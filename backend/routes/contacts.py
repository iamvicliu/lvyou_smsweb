"""Operator address book.

The recipient field used to remember numbers in localStorage only: switching
browsers or clearing site data lost them, and a number could never carry a
name. Contacts live in SQLite instead so the dashboard, the board detail
dialog and the SMS/call lists all resolve the same person.

Numbers are unique across the whole book on purpose. Two contacts sharing one
number would make ``nameOf()`` ambiguous and the suggestion list would offer
the same value twice.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db import Contact, ContactPhone, get_db, nowts

router = APIRouter()

MAX_PHONES = 8
MAX_NAME = 32
MAX_NOTE = 200

_STRIP = re.compile(r"[\s\-()（）.]+")
_PHONE = re.compile(r"^\+?\d{5,20}$")


def normalize_phone(value: Any) -> str:
    """Canonical form: no separators, and mainland +86 folded away.

    Boards report one line as 13…, 8613…, +8613… or 008613…, so storing the
    bare eleven digits is what keeps every lookup stable.
    """
    phone = _STRIP.sub("", str(value or "").strip())
    if phone.startswith("00"):
        phone = "+" + phone[2:]
    if phone.startswith("+86") and len(phone) == 14:
        phone = phone[3:]
    elif phone.startswith("86") and len(phone) == 13:
        phone = phone[2:]
    return phone


def _masked(phone: str) -> str:
    """Never echo a full number back in an error toast."""
    if len(phone) <= 7:
        return "****"
    return f"{phone[:3]}****{phone[-4:]}"


class ContactPhoneIn(BaseModel):
    phone: str = ""
    label: str = ""


class ContactIn(BaseModel):
    name: str = ""
    phones: List[ContactPhoneIn] = []
    note: str = ""
    favorite: bool = False


class FavoriteIn(BaseModel):
    favorite: bool = True


def _clean(db: Session, payload: ContactIn, cid: Optional[int] = None) -> Tuple[str, str, List[Tuple[str, str]]]:
    name = str(payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="联系人姓名不能为空")
    if len(name) > MAX_NAME:
        raise HTTPException(status_code=400, detail=f"姓名最多 {MAX_NAME} 个字")

    note = str(payload.note or "").strip()
    if len(note) > MAX_NOTE:
        raise HTTPException(status_code=400, detail=f"备注最多 {MAX_NOTE} 个字")

    phones: List[Tuple[str, str]] = []
    seen = set()
    for row in payload.phones or []:
        phone = normalize_phone(row.phone)
        if not phone:
            # An empty extra row in the editor is normal, not an error.
            continue
        if not _PHONE.match(phone):
            raise HTTPException(status_code=400, detail=f"号码格式不对：{_masked(phone)}")
        if phone in seen:
            raise HTTPException(status_code=400, detail=f"同一个号码填了两次：{_masked(phone)}")
        seen.add(phone)
        label = str(row.label or "").strip()[:16] or "手机"
        phones.append((phone, label))

    if not phones:
        raise HTTPException(status_code=400, detail="至少填一个号码")
    if len(phones) > MAX_PHONES:
        raise HTTPException(status_code=400, detail=f"一个联系人最多 {MAX_PHONES} 个号码")

    query = db.query(ContactPhone).filter(ContactPhone.phone.in_([p for p, _ in phones]))
    if cid is not None:
        query = query.filter(ContactPhone.contact_id != cid)
    clash = query.first()
    if clash is not None:
        owner = db.query(Contact).filter(Contact.id == clash.contact_id).first()
        raise HTTPException(
            status_code=409,
            detail=f"号码 {_masked(clash.phone)} 已经属于「{owner.name if owner else '其他联系人'}」",
        )

    return name, note, phones


def _dump(db: Session, contact: Contact) -> Dict[str, Any]:
    rows = (
        db.query(ContactPhone)
        .filter(ContactPhone.contact_id == contact.id)
        .order_by(ContactPhone.sort.asc(), ContactPhone.id.asc())
        .all()
    )
    return {
        "id": contact.id,
        "name": contact.name or "",
        "note": contact.note or "",
        "favorite": bool(contact.favorite),
        "phones": [
            {"id": r.id, "phone": r.phone, "label": r.label or "手机"}
            for r in rows
        ],
        "created": int(contact.created or 0),
        "updated": int(contact.updated or 0),
    }


def _replace_phones(db: Session, cid: int, phones: List[Tuple[str, str]]) -> None:
    db.query(ContactPhone).filter(ContactPhone.contact_id == cid).delete()
    for index, (phone, label) in enumerate(phones):
        db.add(ContactPhone(contact_id=cid, phone=phone, label=label, sort=index))


@router.get("/api/contacts")
def list_contacts(q: str = Query("", max_length=64), db: Session = Depends(get_db)):
    """Whole book, favorites first; ``q`` filters by name, note or number."""
    contacts = (
        db.query(Contact)
        .order_by(Contact.favorite.desc(), Contact.name.asc(), Contact.id.asc())
        .all()
    )
    items = [_dump(db, c) for c in contacts]
    needle = str(q or "").strip().lower()
    if needle:
        items = [
            c for c in items
            if needle in c["name"].lower()
            or needle in c["note"].lower()
            or any(needle in p["phone"] for p in c["phones"])
        ]
    return {"items": items, "total": len(items)}


@router.post("/api/contacts")
def create_contact(payload: ContactIn, db: Session = Depends(get_db)):
    name, note, phones = _clean(db, payload)
    now = nowts()
    contact = Contact(
        name=name,
        note=note,
        favorite=1 if payload.favorite else 0,
        created=now,
        updated=now,
    )
    db.add(contact)
    db.flush()
    _replace_phones(db, contact.id, phones)
    db.commit()
    db.refresh(contact)
    return _dump(db, contact)


@router.put("/api/contacts/{cid}")
def update_contact(cid: int, payload: ContactIn, db: Session = Depends(get_db)):
    contact = db.query(Contact).filter(Contact.id == cid).first()
    if contact is None:
        raise HTTPException(status_code=404, detail="联系人不存在")
    name, note, phones = _clean(db, payload, cid=cid)
    contact.name = name
    contact.note = note
    contact.favorite = 1 if payload.favorite else 0
    contact.updated = nowts()
    _replace_phones(db, cid, phones)
    db.commit()
    db.refresh(contact)
    return _dump(db, contact)


@router.delete("/api/contacts/{cid}")
def delete_contact(cid: int, db: Session = Depends(get_db)):
    contact = db.query(Contact).filter(Contact.id == cid).first()
    if contact is None:
        raise HTTPException(status_code=404, detail="联系人不存在")
    db.query(ContactPhone).filter(ContactPhone.contact_id == cid).delete()
    db.delete(contact)
    db.commit()
    return {"ok": True}


@router.post("/api/contacts/{cid}/favorite")
def set_favorite(cid: int, payload: FavoriteIn, db: Session = Depends(get_db)):
    contact = db.query(Contact).filter(Contact.id == cid).first()
    if contact is None:
        raise HTTPException(status_code=404, detail="联系人不存在")
    contact.favorite = 1 if payload.favorite else 0
    contact.updated = nowts()
    db.commit()
    return {"ok": True, "favorite": bool(contact.favorite)}
