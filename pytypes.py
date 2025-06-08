from typing import List, Optional, ClassVar
from pydantic import BaseModel, validator
from enum import Enum

# GMAIL
class GmailResponseTypeEnum(str, Enum):
    draft_mail_for_approval = 'draft_mail_for_approval'
    email_summary = 'email_summary'
    other = 'other'

class email_summary_output(BaseModel):
    summary: str
    subject: str
    from_email: str

class draft_mail_for_approval_output(BaseModel):
    to: List[str]
    subject: str
    body: str


class gmail_output(BaseModel):
    response_type: GmailResponseTypeEnum
    email_summaries: Optional[List[email_summary_output]] = None
    draft_mail_for_approval: Optional[draft_mail_for_approval_output] = None
    other: Optional[str] = None

# Calendar
class CalendarResponseTypeEnum(str, Enum):
    create_event = 'create_event'
    event_summary = 'event_summary'
    other = 'other'

class create_event_output(BaseModel):
    title: str
    description: str
    start_date: str
    end_date: str
    meeting_link: Optional[str] = None

class event_summary_output(BaseModel):
    title: str
    description: str
    start_date: str
    end_date: str
    meeting_link: Optional[str] = None

class calendar_output(BaseModel):
    response_type: CalendarResponseTypeEnum
    create_event: Optional[create_event_output] = None
    event_summary: Optional[List[event_summary_output]] = None
    other: Optional[str] = None

class SlackResponseTypeEnum(str, Enum):
    draft_message_approval = 'draft_message_approval'
    other = 'other'

class draft_message_approval_output(BaseModel):
    message: str
    channel: str

class slack_output(BaseModel):
    response_type: SlackResponseTypeEnum
    draft: Optional[draft_message_approval_output] = None
    other: Optional[str] = None

class NotionResponseTypeEnum(str, Enum):
    notion_response = 'notion_response'

class notion_output(BaseModel):
    response_type: NotionResponseTypeEnum
    notion_response: str
    link_to_document: Optional[str] = None

class WhatsappResponseTypeEnum(str, Enum):
    whatsapp_response = 'whatsapp_response'

class whatsapp_output(BaseModel):
    response_type: WhatsappResponseTypeEnum
    whatsapp_response: str
    
    
    
    