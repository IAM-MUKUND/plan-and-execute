import sys
import os
import pytest

# Add parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.state import AppState, SubTask, ProductState

def test_app_state_product_management():
    state = AppState(user_prompt="Compare Legion 5 and ASUS TUF", category="laptop")
    prod1 = state.get_or_create_product("Lenovo Legion 5")
    assert prod1.name == "Lenovo Legion 5"
    assert "lenovo legion 5" in state.products
    
    state.update_product_specs("Lenovo Legion 5", {"cpu": "Ryzen 7 7840HS", "ram": "16GB"})
    assert state.products["lenovo legion 5"].specs["cpu"] == "Ryzen 7 7840HS"

def test_app_state_dependency_resolution():
    state = AppState(user_prompt="Test dependency")
    t1 = SubTask(id=1, step_type="identify_products", description="Identify products", depends_on=[])
    t2 = SubTask(id=2, step_type="collect_specs", target_product="Legion 5", description="Collect specs", depends_on=[1])
    t3 = SubTask(id=3, step_type="analyze_performance", target_product="Legion 5", description="Analyze perf", depends_on=[2])
    
    state.plan = [t1, t2, t3]
    
    # Step 1 has no dependencies -> should be ready
    assert state.is_step_ready(1) is True
    # Step 2 depends on 1 (not completed yet) -> not ready
    assert state.is_step_ready(2) is False
    
    ready = state.get_ready_steps()
    assert len(ready) == 1
    assert ready[0].id == 1
    
    # Mark Step 1 completed
    state.mark_step_completed(1, result="Identified products")
    assert 1 in state.completed_steps
    assert state.is_step_ready(1) is False  # Completed steps are not 'ready'
    assert state.is_step_ready(2) is True   # Step 2 is now ready!
    assert state.is_step_ready(3) is False  # Step 3 still waiting on 2

def test_app_state_json_serialization():
    state = AppState(user_prompt="Test serialization", category="phone", priority="photography")
    json_str = state.dump_json()
    assert "Test serialization" in json_str
    assert "photography" in json_str
