from enum import Enum
from pydantic import BaseModel, ConfigDict, Field

class Label(str, Enum):
    JOB_POSTINGS = "job_postings"
    CODING_CONTESTS = "coding_contests"
    HACKATHONS = "hackathons"
    FOOD_DELIVERY = "food_delivery"
    NEWSLETTER = "newsletter"
    SECURITY = "security"
    SPAM = "spam"
    DELETE = "delete"
    UNKNOWN = "unknown"


AUTO_SORTED_LABELS = {
    Label.JOB_POSTINGS,
    Label.CODING_CONTESTS,
    Label.HACKATHONS,
    Label.NEWSLETTER,
    Label.SECURITY
}

AUTO_ARCHIVED_LABELS = {Label.SPAM, Label.FOOD_DELIVERY}

HELD_LABELS = {Label.DELETE, Label.UNKNOWN}


class EmailClassifier(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reasoning: str = Field(
            ...,
            min_length=1,
            max_length=280,
            description="One short sentence on why this label was chosen."
        )
    label: Label