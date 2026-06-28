"""Example: Using Page Exploration Tools

This example demonstrates how to use the LangChain tools for page exploration.
"""

from app.agents.page_exploration.tools import (
    playwright_snap_tool,
    playwright_navigate_tool,
    playwright_click_tool,
    playwright_fill_tool,
    check_explored_url_tool,
    update_explored_url_tool,
    write_page_artifact_tool,
)


def example_basic_exploration():
    """Example: Basic page exploration workflow"""

    # Step 1: Navigate to a page
    nav_result = playwright_navigate_tool.invoke({
        "url": "https://app.example.com/workspace/agents",
        "session_id": "exploration-session-001"
    })
    print(f"Navigation: {nav_result}")

    # Step 2: Capture page snapshot
    snap_result = playwright_snap_tool.invoke({
        "url": "https://app.example.com/workspace/agents",
        "session_id": "exploration-session-001"
    })
    print(f"Found {len(snap_result['elements'])} elements")
    print(f"Page title: {snap_result['title']}")

    # Step 3: Check if already explored
    check_result = check_explored_url_tool.invoke({
        "url": "https://app.example.com/workspace/agents",
        "project_id": "proj-123"
    })

    if check_result["explored"]:
        print(f"Page already explored at {check_result['last_explored_at']}")
        return

    # Step 4: Build element locators from snapshot
    elements = []
    for elem in snap_result['elements']:
        if elem['role'] in ['button', 'link', 'textbox']:
            element_data = {
                "id": f"{elem['role']}_{elem['ref']}",
                "name": elem['name'],
                "role": elem['role'],
                "locators": []
            }

            # Generate semantic locator (not using ref!)
            if elem['role'] == 'button':
                locator = {
                    "kind": "role",
                    "code": f"getByRole('button', {{ name: '{elem['name']}' }})",
                    "priority": 1
                }
            elif elem['role'] == 'textbox':
                locator = {
                    "kind": "label",
                    "code": f"getByLabel('{elem['name']}')",
                    "priority": 1
                }
            elif elem['role'] == 'link':
                locator = {
                    "kind": "role",
                    "code": f"getByRole('link', {{ name: '{elem['name']}' }})",
                    "priority": 1
                }

            element_data["locators"].append(locator)
            elements.append(element_data)

    # Step 5: Write page artifact
    artifact_result = write_page_artifact_tool.invoke({
        "url": "https://app.example.com/workspace/agents",
        "title": snap_result['title'],
        "elements": elements,
        "project_id": "proj-123",
        "page_id": "page-workspace-agents"
    })
    print(f"Artifact written: {artifact_result['file_path']}")

    # Step 6: Mark URL as explored
    update_result = update_explored_url_tool.invoke({
        "url": "https://app.example.com/workspace/agents",
        "page_id": "page-workspace-agents",
        "project_id": "proj-123",
        "run_id": "run-001"
    })
    print(f"URL marked as explored: {update_result}")


def example_interactive_exploration():
    """Example: Interactive exploration with clicks and fills"""

    session_id = "interactive-session-001"

    # Navigate to login page
    playwright_navigate_tool.invoke({
        "url": "https://app.example.com/login",
        "session_id": session_id
    })

    # Fill login form
    playwright_fill_tool.invoke({
        "locator": "getByLabel('Email')",
        "value": "test@example.com",
        "session_id": session_id
    })

    playwright_fill_tool.invoke({
        "locator": "getByLabel('Password')",
        "value": "password123",
        "session_id": session_id
    })

    # Click submit button
    click_result = playwright_click_tool.invoke({
        "locator": "getByRole('button', { name: 'Login' })",
        "session_id": session_id
    })

    if click_result['success']:
        print("Login successful")

        # Capture snapshot after login
        snap_result = playwright_snap_tool.invoke({
            "url": "https://app.example.com/dashboard",
            "session_id": session_id
        })
        print(f"Dashboard has {len(snap_result['elements'])} elements")
    else:
        print(f"Login failed: {click_result['error']}")


def example_cross_environment_exploration():
    """Example: Exploring same page in different environments"""

    project_id = "proj-123"

    # Explore in test environment
    test_url = "https://test.app.example.com/workspace/agents"
    snap_result = playwright_snap_tool.invoke({"url": test_url})

    # Write artifact (normalized path will be /workspace/agents)
    write_page_artifact_tool.invoke({
        "url": test_url,
        "title": snap_result['title'],
        "elements": [],
        "project_id": project_id,
        "page_id": "page-workspace-agents"
    })

    update_explored_url_tool.invoke({
        "url": test_url,
        "page_id": "page-workspace-agents",
        "project_id": project_id,
        "run_id": "run-001"
    })

    # Later, check in prod environment
    prod_url = "https://prod.app.example.com/workspace/agents"
    check_result = check_explored_url_tool.invoke({
        "url": prod_url,
        "project_id": project_id
    })

    # Will return explored: True because normalized path matches
    assert check_result["explored"] is True
    print(f"Cross-environment match: {check_result['normalized_path']}")


if __name__ == "__main__":
    print("=== Example 1: Basic Exploration ===")
    example_basic_exploration()

    print("\n=== Example 2: Interactive Exploration ===")
    example_interactive_exploration()

    print("\n=== Example 3: Cross-Environment ===")
    example_cross_environment_exploration()
