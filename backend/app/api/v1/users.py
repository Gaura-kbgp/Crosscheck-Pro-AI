from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.api.dependencies import get_db, get_current_user
from app.schemas.user import UserResponse, AuthenticatedUser, UserUpdateRequest, ChangePasswordRequest
from app.models.core import User
from app.core.exceptions import ResourceNotFoundError
from app.core.security import verify_password, hash_password

router = APIRouter()

@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    stmt = select(User).where(User.id == current_user.user_id)
    user = db.execute(stmt).scalar_one_or_none()
    if not user:
        raise ResourceNotFoundError("User not found")
    return user

@router.patch("/me", response_model=UserResponse)
def update_me(
    request: UserUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    stmt = select(User).where(User.id == current_user.user_id)
    user = db.execute(stmt).scalar_one_or_none()
    if not user:
        raise ResourceNotFoundError("User not found")
        
    if request.full_name is not None:
        user.full_name = request.full_name.strip() or None
        
    db.commit()
    db.refresh(user)
    return user

@router.post("/me/change-password")
def change_password(
    request: ChangePasswordRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    stmt = select(User).where(User.id == current_user.user_id)
    user = db.execute(stmt).scalar_one_or_none()
    if not user:
        raise ResourceNotFoundError("User not found")
        
    # If user has an existing password, verify current password
    if user.password_hash:
        if not request.current_password or not verify_password(request.current_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password does not match"
            )
            
    if len(request.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters"
        )
        
    user.password_hash = hash_password(request.new_password)
    db.commit()
    return {"message": "Password updated successfully"}
