from fastapi import APIRouter
from typing import List
from schemas.user import UserCreate
from models.user import User as UserModel
from services.user_service import UserService
from db.database import SessionLocal

router = APIRouter()
user_service = UserService()

@router.get("/users/{user_type}", response_model=List[UserModel])
async def get_users(user_type: str):
    users = user_service.get_users_by_type(user_type)
    if not users:
        raise HTTPException(status_code=404, detail="Users not found")
    return users
