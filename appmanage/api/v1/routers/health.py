from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
def health_check():
    return {"message": "stackhub API is alive"}
