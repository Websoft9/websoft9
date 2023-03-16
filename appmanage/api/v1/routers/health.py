from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
def health_check():
    return {"message": "StackHub API is alive"}
