from httpx import AsyncClient

from logica.ai.agents.models import AgentName
from logica.modules.users.models import Institution
from tests.integration.conftest import auth_headers, create_group, register_and_login


async def test_default_agents_are_all_enabled(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    group = await create_group(client, teacher_access)

    resp = await client.get(
        f"/ai/groups/{group['id']}/agents", headers=auth_headers(teacher_access)
    )
    assert resp.status_code == 200
    statuses = resp.json()
    # Contra `AgentName` y no contra un número fijo: lo que se está afirmando es
    # "todo agente arranca habilitado" (RF-30), no cuántos agentes hay. Con un
    # `len(statuses) == N` este test se rompía cada vez que una fase agregaba un
    # agente, señalando una regresión donde solo había un enum más largo.
    assert {s["agent_name"] for s in statuses} == {a.value for a in AgentName}
    assert all(s["enabled"] is True for s in statuses)


async def test_student_cannot_toggle_agent(client: AsyncClient, institution: Institution) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")
    group = await create_group(client, teacher_access)

    resp = await client.put(
        f"/ai/groups/{group['id']}/agents/progressive_hint",
        json={"enabled": False},
        headers=auth_headers(student_access),
    )
    assert resp.status_code == 403


async def test_teacher_can_disable_and_reenable_agent(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    group = await create_group(client, teacher_access)

    disable = await client.put(
        f"/ai/groups/{group['id']}/agents/progressive_hint",
        json={"enabled": False},
        headers=auth_headers(teacher_access),
    )
    assert disable.status_code == 200
    assert disable.json()["enabled"] is False

    statuses = (
        await client.get(f"/ai/groups/{group['id']}/agents", headers=auth_headers(teacher_access))
    ).json()
    tutor_status = next(s for s in statuses if s["agent_name"] == "progressive_hint")
    assert tutor_status["enabled"] is False

    reenable = await client.put(
        f"/ai/groups/{group['id']}/agents/progressive_hint",
        json={"enabled": True},
        headers=auth_headers(teacher_access),
    )
    assert reenable.json()["enabled"] is True
