import io


async def test_upload_same_filename_increments_version(client, auth_headers, workspace_id):
    files = {"file": ("report.txt", io.BytesIO(b"version one content"), "text/plain")}
    first = await client.post(
        f"/api/v1/documents/?workspace_id={workspace_id}", files=files, headers=auth_headers
    )
    assert first.status_code == 201
    assert first.json()["version"] == 1

    files = {"file": ("report.txt", io.BytesIO(b"version two content"), "text/plain")}
    second = await client.post(
        f"/api/v1/documents/?workspace_id={workspace_id}", files=files, headers=auth_headers
    )
    assert second.status_code == 201
    assert second.json()["version"] == 2


async def test_upload_same_filename_sets_parent_document_id(client, auth_headers, workspace_id):
    files = {"file": ("notes.txt", io.BytesIO(b"first"), "text/plain")}
    first = await client.post(
        f"/api/v1/documents/?workspace_id={workspace_id}", files=files, headers=auth_headers
    )
    first_id = first.json()["id"]

    files = {"file": ("notes.txt", io.BytesIO(b"second"), "text/plain")}
    second = await client.post(
        f"/api/v1/documents/?workspace_id={workspace_id}", files=files, headers=auth_headers
    )
    assert second.json()["parent_document_id"] == first_id


async def test_upload_third_version_links_to_original_parent(client, auth_headers, workspace_id):
    files = {"file": ("doc.txt", io.BytesIO(b"v1"), "text/plain")}
    first = await client.post(
        f"/api/v1/documents/?workspace_id={workspace_id}", files=files, headers=auth_headers
    )
    first_id = first.json()["id"]

    files = {"file": ("doc.txt", io.BytesIO(b"v2"), "text/plain")}
    await client.post(
        f"/api/v1/documents/?workspace_id={workspace_id}", files=files, headers=auth_headers
    )

    files = {"file": ("doc.txt", io.BytesIO(b"v3"), "text/plain")}
    third = await client.post(
        f"/api/v1/documents/?workspace_id={workspace_id}", files=files, headers=auth_headers
    )
    assert third.json()["version"] == 3
    assert third.json()["parent_document_id"] == first_id


async def test_get_document_versions_returns_all_versions(client, auth_headers, workspace_id):
    files = {"file": ("v.txt", io.BytesIO(b"v1"), "text/plain")}
    first = await client.post(
        f"/api/v1/documents/?workspace_id={workspace_id}", files=files, headers=auth_headers
    )
    first_id = first.json()["id"]

    files = {"file": ("v.txt", io.BytesIO(b"v2"), "text/plain")}
    await client.post(
        f"/api/v1/documents/?workspace_id={workspace_id}", files=files, headers=auth_headers
    )

    response = await client.get(f"/api/v1/documents/{first_id}/versions", headers=auth_headers)
    assert response.status_code == 200
    versions = response.json()
    assert len(versions) == 2
    assert versions[0]["version"] == 1
    assert versions[1]["version"] == 2


async def test_get_document_versions_nonexistent_document_fails(client, auth_headers):
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/api/v1/documents/{fake_id}/versions", headers=auth_headers)
    assert response.status_code == 404


async def test_get_document_versions_another_users_workspace_fails(client, auth_headers, workspace_id):
    files = {"file": ("private.txt", io.BytesIO(b"data"), "text/plain")}
    upload = await client.post(
        f"/api/v1/documents/?workspace_id={workspace_id}", files=files, headers=auth_headers
    )
    document_id = upload.json()["id"]

    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "otheruser@test.com",
            "password": "testpassword123",
            "full_name": "Other User",
            "workspace_name": "Other Workspace",
        },
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "otheruser@test.com", "password": "testpassword123"},
    )
    other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = await client.get(f"/api/v1/documents/{document_id}/versions", headers=other_headers)
    assert response.status_code == 403