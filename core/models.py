from pydantic import BaseModel, Field, conlist
from typing import List, Optional


class ActionItem(BaseModel):
    """
    Schema for a single extracted task.
    Used to enforce the structure for the Action Item Extraction Prompt's JSON output.
    """
    task: str = Field(..., description="The actionable request or task extracted from the email body.")
    deadline: str = Field(..., description="The specified deadline (e.g., 'EOD Monday', '2025-12-01') or 'None' if not found.")

class ActionItemList(BaseModel):
    """A wrapper model to define the expected output as a list of ActionItem."""
    action_items: List[ActionItem]
    

class EmailRecord(BaseModel):
    """
    Schema for a single email item in the Mock Inbox.
    Includes initial data and fields for storing processed output.
    """
    # Raw Data from mock_inbox.json
    id: int
    sender: str
    subject: str
    timestamp: str
    body: str
    is_read: bool = False

    # Processed Data (filled by the LLM Agent)
    category: str = Field("", description="The categorized tag: Important, Newsletter, Spam, To-Do, etc.")
    action_items: List[ActionItem] = Field([], description="A list of structured tasks extracted from the email.")
    draft_reply: str = Field("", description="The text of the auto-generated draft reply.")


class PromptTemplate(BaseModel):
    """
    Schema for a single prompt configuration saved in the 'Prompt Brain' panel.
    """
    name: str = Field(..., description="The user-friendly name of the prompt (e.g., Categorization_Prompt).")
    description: str = Field(..., description="A short description for the UI.")
    template: str = Field(..., description="The full, detailed text prompt given to the LLM.")
    output_format: str = Field(..., description="Expected output format: 'text' or 'json'.")
    json_schema: Optional[str] = Field(None, description="If output_format is 'json', the required JSON structure.")



class PromptConfiguration(BaseModel):
    """
    Schema for the entire set of prompts loaded from the configuration file.
    """
    Categorization_Prompt: PromptTemplate
    Action_Extraction_Prompt: PromptTemplate
    Auto_Reply_Prompt: PromptTemplate