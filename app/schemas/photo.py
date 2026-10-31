from pydantic import BaseModel

class PhotoOut(BaseModel):
    id: int
    url: str


class PhotosResponseSchema(BaseModel):
    photos: list[PhotoOut]