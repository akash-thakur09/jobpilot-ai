from typing import Dict, Type
from backend.app.collectors.base import BaseJobSourceAdapter, RawJobData, NormalizedJob
from backend.app.collectors.synthetic import SyntheticJobAdapter
from backend.app.collectors.greenhouse import GreenhouseJobAdapter
from backend.app.collectors.lever import LeverJobAdapter
from backend.app.collectors.naukri import NaukriJobAdapter
from backend.app.collectors.instahyre import InstahyreJobAdapter
from backend.app.collectors.cutshort import CutshortJobAdapter
from backend.app.collectors.hirist import HiristJobAdapter
from backend.app.collectors.foundit import FounditJobAdapter
from backend.app.collectors.linkedin import LinkedInJobAdapter
from backend.app.collectors.indeed import IndeedJobAdapter

ADAPTER_REGISTRY: Dict[str, Type[BaseJobSourceAdapter]] = {
    "synthetic": SyntheticJobAdapter,
    "greenhouse": GreenhouseJobAdapter,
    "lever": LeverJobAdapter,
    "naukri": NaukriJobAdapter,
    "instahyre": InstahyreJobAdapter,
    "cutshort": CutshortJobAdapter,
    "hirist": HiristJobAdapter,
    "foundit": FounditJobAdapter,
    "linkedin": LinkedInJobAdapter,
    "indeed": IndeedJobAdapter,
}


def get_adapter(source_identifier: str) -> BaseJobSourceAdapter:
    """Returns an instance of the registered adapter for the given source identifier."""
    adapter_cls = ADAPTER_REGISTRY.get(source_identifier.lower())
    if not adapter_cls:
        raise ValueError(
            f"Unsupported job source identifier: '{source_identifier}'. Supported sources: {list(ADAPTER_REGISTRY.keys())}"
        )
    return adapter_cls()


__all__ = [
    "BaseJobSourceAdapter",
    "RawJobData",
    "NormalizedJob",
    "SyntheticJobAdapter",
    "GreenhouseJobAdapter",
    "LeverJobAdapter",
    "NaukriJobAdapter",
    "InstahyreJobAdapter",
    "CutshortJobAdapter",
    "HiristJobAdapter",
    "FounditJobAdapter",
    "LinkedInJobAdapter",
    "IndeedJobAdapter",
    "ADAPTER_REGISTRY",
    "get_adapter",
]
