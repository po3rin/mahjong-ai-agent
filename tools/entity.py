from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ScoreResponse(BaseModel):
    han: Optional[int] = Field(None, description="Number of han")
    fu: Optional[int] = Field(None, description="Number of fu")
    score: Optional[int] = Field(None, description="Score points")
    yaku: Optional[List[str]] = Field(None, description="List of yaku")
    fu_details: Optional[List[Dict[str, Any]]] = Field(
        None, description="Fu calculation details"
    )
    error: Optional[str] = Field(None, description="Error message")
