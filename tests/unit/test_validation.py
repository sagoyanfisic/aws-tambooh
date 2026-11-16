import pytest
from pydantic import ValidationError

from backend.common.models.domain import MealPlanRequest


def test_household_bounds():
    with pytest.raises(ValidationError):
        MealPlanRequest(household_size=0)
