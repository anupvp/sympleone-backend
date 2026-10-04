from pydantic import BaseModel


class SellerCountOut(BaseModel):
    total: int
