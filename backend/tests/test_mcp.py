from __future__ import annotations

import asyncio

from mcp import Client

from scripts import gamma_mcp


def test_mcp_exposes_grounded_agent_tools(monkeypatch) -> None:
    calls: list[tuple[str, str, dict]] = []

    def fake_request(method: str, path: str, **kwargs):
        calls.append((method, path, kwargs))
        if path == "/api/projects":
            return [{"id": "prj_test", "title": "Proyecto"}]
        if path.endswith("/context"):
            return {"project": {"id": "prj_test"}, "pending_criteria": []}
        return {"status": "ok"}

    monkeypatch.setattr(gamma_mcp.api, "request", fake_request)

    async def exercise_server() -> None:
        async with Client(gamma_mcp.mcp) as client:
            listed = await client.list_tools()
            tools = {tool.name: tool for tool in listed.tools}
            assert set(tools) == {
                "list_projects",
                "get_project_context",
                "create_project",
                "update_outline",
                "update_criteria",
                "attach_source",
                "search_project_sources",
                "remember_project_decision",
                "update_section",
                "attach_artifact",
                "register_execution",
                "request_audit",
                "export_docx",
                "package_submission",
            }
            assert tools["list_projects"].annotations.read_only_hint is True
            assert tools["search_project_sources"].annotations.read_only_hint is True
            assert tools["create_project"].annotations.read_only_hint is False
            assert tools["update_outline"].annotations.read_only_hint is False
            assert tools["update_criteria"].annotations.read_only_hint is False
            assert tools["attach_source"].annotations.read_only_hint is False
            assert tools["update_section"].annotations.read_only_hint is False
            assert tools["update_section"].annotations.destructive_hint is False
            assert tools["export_docx"].annotations.read_only_hint is False
            assert tools["package_submission"].annotations.read_only_hint is False

            projects = await client.call_tool("list_projects", {})
            assert projects.structured_content == {"result": [{"id": "prj_test", "title": "Proyecto"}]}
            context = await client.call_tool("get_project_context", {"project_id": "prj_test"})
            assert context.structured_content["project"]["id"] == "prj_test"
            outline = await client.call_tool("update_outline", {
                "project_id": "prj_test",
                "outline": [{"title": "Introducción", "description": "Contexto general"}],
            })
            assert outline.structured_content["status"] == "ok"
            criteria_res = await client.call_tool("update_criteria", {
                "project_id": "prj_test",
                "criteria": [{"criterion": "Rúbrica 1", "indicator": "Indicador 1", "points": 10.0}],
            })
            assert criteria_res.structured_content["status"] == "ok"
            updated = await client.call_tool("update_section", {
                "project_id": "prj_test",
                "heading": "Desarrollo",
                "content_html": "<p>Contenido</p>",
            })
            assert updated.structured_content["status"] == "ok"
            exported = await client.call_tool("export_docx", {"project_id": "prj_test"})
            assert exported.structured_content["status"] == "ok"
            packaged = await client.call_tool("package_submission", {"project_id": "prj_test"})
            assert packaged.structured_content["status"] == "ok"

    asyncio.run(exercise_server())
    assert calls[0][:2] == ("GET", "/api/projects")
    assert calls[1][:2] == ("GET", "/api/agent/projects/prj_test/context")
    assert calls[2][:2] == ("PUT", "/api/projects/prj_test/outline")
    assert calls[3][:2] == ("PUT", "/api/projects/prj_test/criteria")
    assert calls[4][0:2] == ("PATCH", "/api/projects/prj_test/section")
    assert calls[4][2]["json"]["create_snapshot"] is True

