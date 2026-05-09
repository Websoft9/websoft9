from typing import Literal, Optional

from pydantic import BaseModel, Field


class OverviewTaskItem(BaseModel):
    key: str = Field(..., description="Stable task identifier")
    kind: str = Field(..., description="Task kind, such as app-install or proxy")
    title: str = Field(..., description="Short task title")
    status: Literal["running", "success", "failed"] = Field(..., description="Normalized task status")
    detail: Optional[str] = Field(default=None, description="Compact task detail")
    updated_at: str = Field(..., description="Task update timestamp in UTC ISO format")
    target_route: str = Field(..., description="Owning module route")


class OverviewAlert(BaseModel):
    key: str = Field(..., description="Stable alert identifier")
    level: Literal["info", "warning", "error"] = Field(..., description="Alert severity")
    title: str = Field(..., description="Short alert title")
    detail: Optional[str] = Field(default=None, description="Alert detail")
    target_route: str = Field(..., description="Recommended next route")


class OverviewProductSummary(BaseModel):
    available: bool = Field(default=True, description="Whether product summary loaded successfully")
    unavailable_reason: Optional[str] = Field(default=None, description="Reason when summary is unavailable")
    version: Optional[str] = Field(default=None, description="Current product version")
    edition_key: Optional[str] = Field(default=None, description="Current edition key")
    edition_name: Optional[str] = Field(default=None, description="Current edition display name")
    catalog_app_count: Optional[int] = Field(default=None, description="Total application count exposed in the App Store")
    installed_count: Optional[int] = Field(default=None, description="Installed application count")
    available_app_count: Optional[int] = Field(default=None, description="Available application count for the current product edition")
    upgrade_state: str = Field(default="unknown", description="Compact upgrade state")
    target_route: str = Field(default="/settings", description="Owning module route")


class OverviewHostSummary(BaseModel):
    available: bool = Field(default=True, description="Whether host summary loaded successfully")
    unavailable_reason: Optional[str] = Field(default=None, description="Reason when host summary is unavailable")
    hostname: Optional[str] = Field(default=None, description="Host name")
    os_name: Optional[str] = Field(default=None, description="Host operating system display name")
    kernel_version: Optional[str] = Field(default=None, description="Host kernel version")
    architecture: Optional[str] = Field(default=None, description="Host CPU architecture")
    uptime_seconds: Optional[int] = Field(default=None, description="Host uptime in seconds")
    target_route: str = Field(default="/services", description="Owning module route")


class OverviewRuntimeSummary(BaseModel):
    available: bool = Field(default=True, description="Whether runtime resource summary loaded successfully")
    unavailable_reason: Optional[str] = Field(default=None, description="Reason when runtime summary is unavailable")
    runtime_scope: Literal["container", "system"] = Field(default="system", description="Whether runtime metrics were sourced from cgroup/container scope or system scope")
    health_state: Literal["healthy", "warning", "critical"] = Field(default="healthy", description="Overall runtime health state")
    cpu_percent: Optional[float] = Field(default=None, description="Approximate CPU load percent")
    cpu_cores: Optional[int] = Field(default=None, description="Logical CPU cores available to the runtime")
    cpu_quota_cores: Optional[float] = Field(default=None, description="Container CPU quota in cores when a cgroup limit is available")
    memory_percent: Optional[float] = Field(default=None, description="Current memory usage percent")
    memory_used_bytes: Optional[int] = Field(default=None, description="Current memory used bytes")
    memory_total_bytes: Optional[int] = Field(default=None, description="Current memory total bytes")
    network_rx_rate_bytes: Optional[int] = Field(default=None, description="Current inbound network traffic rate in bytes per second")
    network_tx_rate_bytes: Optional[int] = Field(default=None, description="Current outbound network traffic rate in bytes per second")
    network_rx_bytes: Optional[int] = Field(default=None, description="Current total inbound network bytes from container interfaces")
    network_tx_bytes: Optional[int] = Field(default=None, description="Current total outbound network bytes from container interfaces")
    disk_percent: Optional[float] = Field(default=None, description="Current root filesystem usage percent")
    disk_used_bytes: Optional[int] = Field(default=None, description="Current root filesystem used bytes")
    disk_total_bytes: Optional[int] = Field(default=None, description="Current root filesystem total bytes")


class OverviewAppsSummary(BaseModel):
    available: bool = Field(default=True, description="Whether app summary loaded successfully")
    unavailable_reason: Optional[str] = Field(default=None, description="Reason when app summary is unavailable")
    installed_count: int = Field(default=0, description="Installed app count")
    active_count: int = Field(default=0, description="Active app count")
    inactive_count: int = Field(default=0, description="Inactive app count")
    installing_count: int = Field(default=0, description="Installing app count")
    error_count: int = Field(default=0, description="Errored app count")
    target_route: str = Field(default="/myapps", description="Owning module route")


class OverviewServicesSummary(BaseModel):
    available: bool = Field(default=True, description="Whether service summary loaded successfully")
    unavailable_reason: Optional[str] = Field(default=None, description="Reason when service summary is unavailable")
    total_count: int = Field(default=0, description="Total bundled services count")
    healthy_count: int = Field(default=0, description="Healthy service count")
    degraded_count: int = Field(default=0, description="Degraded service count")
    unavailable_count: int = Field(default=0, description="Unavailable service count")
    target_route: str = Field(default="/services", description="Owning module route")


class OverviewTasksSummary(BaseModel):
    available: bool = Field(default=True, description="Whether task summary loaded successfully")
    unavailable_reason: Optional[str] = Field(default=None, description="Reason when task summary is unavailable")
    items: list[OverviewTaskItem] = Field(default_factory=list, description="Recent task summary items")
    target_route: str = Field(default="/myapps", description="Default owning module route")


class OverviewResponse(BaseModel):
    generated_at: str = Field(..., description="Overview generation timestamp in UTC ISO format")
    product: OverviewProductSummary
    host: OverviewHostSummary
    apps: OverviewAppsSummary
    runtime: OverviewRuntimeSummary
    host_runtime: OverviewRuntimeSummary
    services: OverviewServicesSummary
    tasks: OverviewTasksSummary
    alerts: list[OverviewAlert] = Field(default_factory=list, description="Compact homepage alerts")
