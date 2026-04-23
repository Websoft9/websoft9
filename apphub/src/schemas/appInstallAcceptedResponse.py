from pydantic import BaseModel, Field


class AppInstallAcceptedResponse(BaseModel):
    message: str = Field(..., description="Result message", example="Success")
    details: str = Field(..., description="Result details", example="The app is installing and can be viewed through 'My Apps.'")
    app_id: str = Field(..., description="Resolved installed app ID", example="wordpress_ab123")
    tracking_id: str = Field(..., description="Installation tracking ID", example="d290f1ee-6c54-4b01-90e6-d701748f0851")