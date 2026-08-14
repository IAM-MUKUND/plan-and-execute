import json
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any

class SubTask(BaseModel):
    id: int
    step_type: str  # identify_products, collect_specs, collect_pricing, analyze_performance, generate_recommendation
    target_product: Optional[str] = None
    description: str
    depends_on: List[int] = Field(default_factory=list)
    status: str = "pending"  # pending, in_progress, completed, failed
    result: Optional[Any] = None

class ProductState(BaseModel):
    name: str
    category: str = "laptop"
    specs: Optional[Dict[str, Any]] = None
    pricing: Optional[Dict[str, Any]] = None
    performance: Optional[Dict[str, Any]] = None

class AppState(BaseModel):
    user_prompt: str
    category: str = "laptop"  # laptop or phone
    priority: str = "general" # gaming, ML, photography, battery, general, budget
    budget: Optional[int] = None
    target_products: List[str] = Field(default_factory=list)
    products: Dict[str, ProductState] = Field(default_factory=dict)
    plan: List[SubTask] = Field(default_factory=list)
    completed_steps: List[int] = Field(default_factory=list)

    def get_or_create_product(self, product_name: str) -> ProductState:
        key = product_name.strip().lower()
        if key not in self.products:
            self.products[key] = ProductState(name=product_name, category=self.category)
        return self.products[key]

    def update_product_specs(self, product_name: str, specs_data: Dict[str, Any]):
        prod = self.get_or_create_product(product_name)
        prod.specs = specs_data

    def update_product_pricing(self, product_name: str, pricing_data: Dict[str, Any]):
        prod = self.get_or_create_product(product_name)
        prod.pricing = pricing_data

    def update_product_performance(self, product_name: str, perf_data: Dict[str, Any]):
        prod = self.get_or_create_product(product_name)
        prod.performance = perf_data

    def mark_step_completed(self, step_id: int, result: Optional[Any] = None):
        if step_id not in self.completed_steps:
            self.completed_steps.append(step_id)
        for task in self.plan:
            if task.id == step_id:
                task.status = "completed"
                task.result = result

    def is_step_ready(self, step_id: int) -> bool:
        for task in self.plan:
            if task.id == step_id:
                if task.status == "completed":
                    return False
                return all(dep in self.completed_steps for dep in task.depends_on)
        return False

    def get_ready_steps(self) -> List[SubTask]:
        return [task for task in self.plan if self.is_step_ready(task.id)]

    def dump_json(self, filepath: Optional[str] = None) -> str:
        data_str = self.model_dump_json(indent=2)
        if filepath:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(data_str)
        return data_str
