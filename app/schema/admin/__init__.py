from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class ForcePasswordResetUpdate(BaseModel):
    """Schema for updating forced password reset date"""
    force_reset_date: Optional[int] = Field(None, description="Unix timestamp of the force reset date. Use 0 to disable.")

class SecuritySettingsRead(BaseModel):
    """Schema for reading security settings"""
    force_password_reset_date: Optional[int] = None
    last_updated: Optional[datetime] = None
