import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any
from backend.state import AppState

logger = logging.getLogger("logger_util")

def save_execution_log(state: AppState, final_recommendation: str, duration_seconds: float) -> str:
    """
    Dumps execution run log to CAT-1/backend/logs/{timestamp}.json.
    Returns relative/absolute filepath.
    """
    logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(logs_dir, exist_ok=True)

    now_utc = datetime.now(timezone.utc)
    timestamp_str = now_utc.strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp_str}.json"
    filepath = os.path.join(logs_dir, filename)

    products_data = {}
    for key, pstate in state.products.items():
        products_data[pstate.name] = {
            "specs": pstate.specs,
            "pricing": pstate.pricing,
            "performance": pstate.performance
        }

    log_payload = {
        "timestamp": now_utc.isoformat(),
        "user_prompt": state.user_prompt,
        "category": state.category,
        "priority": state.priority,
        "budget": state.budget,
        "target_products": state.target_products,
        "plan": [task.model_dump() for task in state.plan],
        "products_data": products_data,
        "completed_steps": state.completed_steps,
        "final_recommendation": final_recommendation,
        "execution_time_seconds": round(duration_seconds, 2)
    }

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(log_payload, f, indent=2)
        logger.info(f"Successfully saved execution log to: {filepath}")
    except Exception as e:
        logger.error(f"Failed to save execution log: {e}")

    return filepath
