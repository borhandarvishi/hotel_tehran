from typing import Literal

from pydantic import BaseModel, Field


TehranZone = Literal["شمال", "جنوب", "شرق", "غرب", "مرکز"]


class FindHotelInput(BaseModel):
  """Structured preferences extracted from the conversation for hotel search."""

  hotel_name: str | None = Field(
    default=None,
    description="Specific hotel name if the user mentioned one.",
  )
  facilities_preferences: str | None = Field(
    default=None,
    description="Desired hotel facilities (parking, wifi, restaurant, etc.).",
  )
  address: str | None = Field(
    default=None,
    description="Address or area preference beyond zone (street, landmark).",
  )
  general_preferences: str | None = Field(
    default=None,
    description="General preferences: budget, vibe, trip purpose, family, quiet, etc.",
  )
  location: TehranZone | None = Field(
    default=None,
    description="Tehran zone: شمال، جنوب، شرق، غرب، مرکز",
  )
  star: int | None = Field(
    default=None,
    ge=0,
    le=5,
    description="Minimum or exact star rating if user cares (1-5).",
  )


class RankHotelsOutput(BaseModel):
  hotel_ids: list[str] = Field(
    max_length=5,
    description="Up to 5 hotel_id values most relevant to the user request.",
  )
  reasoning: str = Field(description="Brief Persian explanation of selection.")
