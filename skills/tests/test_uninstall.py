import pytest

from skills.installer import (
    InstallError,
    _validate_skill_name,
)
from skills import envelope as e


def test_validate_skill_name_accepts_normal_names():
    _validate_skill_name('coding-guide')
    _validate_skill_name('webapp_testing')
    _validate_skill_name('skill.v2')
    _validate_skill_name('A-Bc_1.2')


@pytest.mark.parametrize('bad', [
    '',
    '..',
    '.',
    '...',
    '../etc',
    'a/b',
    'a\\b',
    'has space',
    'has;semi',
    'has$dollar',
    'has`backtick',
])
def test_validate_skill_name_rejects_traversal_and_specials(bad):
    with pytest.raises(InstallError) as ex:
        _validate_skill_name(bad)
    assert ex.value.http_status == 400
    assert ex.value.code == e.UNINSTALL_SKILL_NAME_INVALID
