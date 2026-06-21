from pydantic import BaseModel, Field


class LoginFormAnalysisOutput(BaseModel):
    username_element_id: str = Field(default="")
    password_element_id: str = Field(default="")
    captcha_image_element_id: str = Field(default="")
    captcha_input_element_id: str = Field(default="")
    agreement_element_id: str | None = None
    login_button_element_id: str = Field(default="")
