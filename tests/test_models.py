from app.modules.clients.infrastructure.models import ClientModel
from app.modules.identity.infrastructure.models import TenantModel, UserModel, UserRole
from app.modules.proposals.infrastructure.models import (
    ProposalModel,
    ProposalStatus,
    ProposalType,
)


def test_identity_models_have_expected_table_names_and_constraints():
    assert TenantModel.__tablename__ == "tenants"
    assert UserModel.__tablename__ == "users"
    assert UserRole.ADMIN.value == "admin"
    assert UserRole.OPERATOR.value == "operator"
    assert UserModel.__table_args__[0].name == "uq_users_tenant_id_email"


def test_client_model_has_expected_table_name_and_unique_constraint():
    assert ClientModel.__tablename__ == "clients"
    assert ClientModel.__table_args__[0].name == "uq_clients_tenant_id_cpf"


def test_proposal_model_and_enums_match_expected_domain_values():
    assert ProposalModel.__tablename__ == "proposals"
    assert ProposalType.SIMULATION.value == "simulacao"
    assert ProposalType.PROPOSAL.value == "proposta"
    assert ProposalStatus.PENDING.value == "pending"
    assert ProposalStatus.APPROVED.value == "approved"
