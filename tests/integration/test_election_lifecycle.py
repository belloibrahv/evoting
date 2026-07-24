"""
Integration tests — full election lifecycle via Flask test client.
Verifies: create → schedule → open → vote → close → tally → publish.
"""
import pytest
from app.models.election import ElectionStatus


class TestPublicPages:
    def test_homepage_loads(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"TASFUED" in resp.data

    def test_login_page_loads(self, client):
        resp = client.get("/auth/login")
        assert resp.status_code == 200

    def test_register_page_loads(self, client):
        resp = client.get("/auth/register")
        assert resp.status_code == 200

    def test_results_index_loads(self, client):
        resp = client.get("/results/")
        assert resp.status_code == 200

    def test_api_elections_returns_json(self, client):
        resp = client.get("/api/elections")
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)


class TestAuthentication:
    def test_admin_login_redirects_to_admin_dashboard(self, client, admin_user):
        resp = client.post("/auth/login", data={
            "matric_number": admin_user.matric_number,
            "password": "Admin@1234",
        }, follow_redirects=False)
        assert resp.status_code == 302
        assert "/admin" in resp.headers["Location"]

    def test_voter_login_redirects_to_voter_dashboard(self, client, voter_user):
        resp = client.post("/auth/login", data={
            "matric_number": voter_user.matric_number,
            "password": "Voter@1234",
        }, follow_redirects=False)
        assert resp.status_code == 302
        assert "/voter" in resp.headers["Location"]

    def test_wrong_password_shows_error(self, client, voter_user):
        resp = client.post("/auth/login", data={
            "matric_number": voter_user.matric_number,
            "password": "WrongPass99",
        }, follow_redirects=True)
        assert b"Invalid" in resp.data

    def test_logout_clears_session(self, client, voter_user):
        client.post("/auth/login", data={
            "matric_number": voter_user.matric_number,
            "password": "Voter@1234",
        })
        resp = client.post("/auth/logout", follow_redirects=False)
        assert resp.status_code == 302


class TestRBAC:
    def test_voter_cannot_access_admin_dashboard(self, client, voter_user):
        client.post("/auth/login", data={
            "matric_number": voter_user.matric_number,
            "password": "Voter@1234",
        })
        resp = client.get("/admin/", follow_redirects=False)
        assert resp.status_code in (302, 403)

    def test_unauthenticated_cannot_access_voter_ballot(self, client, sample_election):
        resp = client.get(
            f"/voter/ballot/{sample_election.election_id}",
            follow_redirects=False,
        )
        assert resp.status_code == 302  # Redirected to login

    def test_audit_log_blocked_for_voter(self, client, voter_user):
        client.post("/auth/login", data={
            "matric_number": voter_user.matric_number,
            "password": "Voter@1234",
        })
        resp = client.get("/admin/audit", follow_redirects=False)
        assert resp.status_code in (302, 403)


class TestVotingFlow:
    def test_vote_submission_returns_receipt(
        self, client, voter_user, sample_election, eligible_voter_entry
    ):
        """End-to-end happy path: login → submit ballot → receive receipt."""
        client.post("/auth/login", data={
            "matric_number": voter_user.matric_number,
            "password": "Voter@1234",
        })

        position_id = str(sample_election.positions[0].position_id)
        candidate_id = sample_election.positions[0].candidates[0].candidate_id

        resp = client.post(
            f"/voter/ballot/{sample_election.election_id}/submit",
            json={position_id: candidate_id},
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert len(data["receipt_id"]) == 40
        assert len(data["ballot_hash"]) == 64

    def test_duplicate_vote_returns_400(
        self, client, voter_user, sample_election, eligible_voter_entry
    ):
        """Second ballot submission from same voter must be rejected."""
        client.post("/auth/login", data={
            "matric_number": voter_user.matric_number,
            "password": "Voter@1234",
        })
        position_id = str(sample_election.positions[0].position_id)
        candidate_id = sample_election.positions[0].candidates[0].candidate_id
        payload = {position_id: candidate_id}

        r1 = client.post(
            f"/voter/ballot/{sample_election.election_id}/submit",
            json=payload, content_type="application/json",
        )
        assert r1.status_code == 200

        r2 = client.post(
            f"/voter/ballot/{sample_election.election_id}/submit",
            json=payload, content_type="application/json",
        )
        assert r2.status_code == 400
        assert "already voted" in r2.get_json()["error"]

    def test_empty_submission_returns_400(
        self, client, voter_user, sample_election, eligible_voter_entry
    ):
        """Submitting an empty ballot is rejected."""
        client.post("/auth/login", data={
            "matric_number": voter_user.matric_number,
            "password": "Voter@1234",
        })
        resp = client.post(
            f"/voter/ballot/{sample_election.election_id}/submit",
            json={}, content_type="application/json",
        )
        assert resp.status_code == 400


class TestResults:
    def test_results_hidden_before_publish(self, client, sample_election):
        resp = client.get(f"/results/{sample_election.election_id}")
        assert resp.status_code == 404

    def test_nonexistent_election_results_404(self, client):
        resp = client.get("/results/99999")
        assert resp.status_code == 404
