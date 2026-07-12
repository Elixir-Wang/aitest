from pydantic import BaseModel, Field


class LoginFormAnalysisOutput(BaseModel):
    username_element_id: str = ""
    password_element_id: str = ""
    captcha_image_element_id: str = ""
    captcha_input_element_id: str = ""
    agreement_element_id: str | None = Field(default=None)
    login_button_element_id: str = ""
