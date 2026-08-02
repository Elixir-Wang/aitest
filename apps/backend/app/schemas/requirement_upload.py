from pydantic import BaseModel, Field, field_validator


class RequirementUploadFileIn(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    size: int = Field(gt=0)
    sha256: str = Field(default="", max_length=64)

    @field_validator("filename")
    @classmethod
    def filename_must_not_be_a_path(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or "/" in normalized or "\\" in normalized:
            raise ValueError("文件名不合法")
        return normalized

    @field_validator("sha256")
    @classmethod
    def sha256_must_be_hex(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized and (len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized)):
            raise ValueError("sha256 格式不正确")
        return normalized


class RequirementUploadSessionCreateIn(BaseModel):
    mode: str = Field(default="new", pattern="^(new|append)$")
    document_name: str = Field(default="", max_length=200)
    existing_document_id: str = Field(default="", max_length=100)
    project_version_id: str = Field(default="", max_length=100)
    files: list[RequirementUploadFileIn] = Field(min_length=1)
