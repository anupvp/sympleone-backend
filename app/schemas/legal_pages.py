from pydantic import BaseModel, Field


class LegalSection(BaseModel):
    heading: str
    body: str


class LegalPageResponse(BaseModel):
    slug: str
    title: str
    last_updated: str = Field(description="ISO date the page content was last revised.")
    summary: str
    sections: list[LegalSection]
    contact_email: str | None = None
