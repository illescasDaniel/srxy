"""Installer GPU probe — re-exports the shared torch-free detector."""

from __future__ import annotations

from srxy.application.gpu_availability import (
	has_accelerated_gpu,
	has_nvidia_gpu,
	nvidia_device_nodes_present,
	nvidia_smi_available,
	nvidia_smi_reports_gpu,
)


__all__ = [
	"has_accelerated_gpu",
	"has_nvidia_gpu",
	"nvidia_device_nodes_present",
	"nvidia_smi_available",
	"nvidia_smi_reports_gpu",
]
