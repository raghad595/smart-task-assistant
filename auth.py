"""
This file code main task is to make sure that this user is allowed to assign a task to other employee 
but before that it make sure he even exists (both sender & assigned).

"""

VALID_ROLES = ("مدير", "مشرف", "موظف")
VALID_DEPARTMENTS = ("الإدارة", "المشاريع", "المالية")


def can_assign_task(sender: dict, assignee: dict) -> bool:
    """
    This function specifically checks whether the sender is allowed to assign a task
    to the specified employee.

    Both dictionaries must represent valid employee records
    retrieved from the database.

    Returns:
        True: Assignment is allowed.
        False: Assignment is rejected.
    """

    # Search both sender and assignee in the DB.
    if not isinstance(sender, dict) or not isinstance(assignee, dict): 
        return False
    # Retrieve required keys to be used in the permission check.
    required_keys = ("id", "role", "department")

    for employee in (sender, assignee):
        # if any required key is missing, reject the assignment.
        if any(key not in employee for key in required_keys): 
            return False

        # If the ID is missing or invalid, reject the assignment (ID must be a positive integer).
        if type(employee["id"]) is not int or employee["id"] <= 0:
            return False
        
        # role and department must be valid values (determined according to the business rules).
        if employee["role"] not in VALID_ROLES:
            return False

        if employee["department"] not in VALID_DEPARTMENTS:
            return False

    # A manager can assign tasks to anyone, a supervisor can assign tasks within their department, and an employee can only assign tasks to himself (used arabic keywords).
    if sender["role"] == "مدير":
        return True

    if sender["role"] == "مشرف":
        return sender["department"] == assignee["department"]

    if sender["role"] == "موظف":
        return sender["id"] == assignee["id"]

    # not any of these roles? reject the assignment.
    return False


if __name__ == "__main__":
    # Mock records used only for testing before connecting the database.
    manager_munira = {
        "id": 1,
        "role": "مدير",
        "department": "الإدارة",
    }

    supervisor_sara = {
        "id": 2,
        "role": "مشرف",
        "department": "المشاريع",
    }

    employee_fahad = {
        "id": 3,
        "role": "موظف",
        "department": "المشاريع",
    }

    employee_khalid = {
        "id": 4,
        "role": "موظف",
        "department": "المشاريع",
    }

    employee_noura = {
        "id": 5,
        "role": "موظف",
        "department": "المالية",
    }

    # T01: Supervisor assigns to an employee in the same department.
    assert can_assign_task(supervisor_sara, employee_khalid) is True

    # T02: Employee attempts to assign to another employee (rejected).
    assert can_assign_task(employee_fahad, employee_khalid) is False

    # T04: Supervisor attempts to assign across departments.
    assert can_assign_task(supervisor_sara, employee_noura) is False

    # T09: Manager assigns to an employee in another department.
    assert can_assign_task(manager_munira, employee_noura) is True

    # Employee assigns to himself.
    assert can_assign_task(employee_fahad, employee_fahad) is True

    # Unknown or malformed role is rejected.
    unknown_role = {
        "id": 7,
        "role": "مدير مزيف",
        "department": "المشاريع",
    }

    assert can_assign_task(unknown_role, employee_khalid) is False

    # Missing employee information is rejected.
    assert can_assign_task({}, employee_khalid) is False
