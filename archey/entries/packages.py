"""Number of installed packages detection class"""

import os

from subprocess import check_output, DEVNULL, CalledProcessError

from archey.entry import Entry
from archey.distributions import Distributions


def get_homebrew_cellar_path() -> str:
    """Return Homebrew Cellar path (if available)"""
    try:
        return check_output(
            ['brew', '--cellar'],
            stderr=DEVNULL,
            universal_newlines=True
        ).rstrip()
    except (FileNotFoundError, PermissionError, CalledProcessError):
        pass

    return '/usr/local/Cellar/'


PACKAGES_TOOLS = (
    {'cmd': ('apk', 'list', '--installed')},
    # As of 2020, `apt` is _very_ slow compared to `dpkg` on Debian-based distributions.
    # Additional note : `apt`'s CLI is currently not "stable" in Debian terms.
    # If `apt` happens to be preferred over `dpkg` in the future, don't forget to remove the latter.
    #{'cmd': ('apt', 'list', '-qq', '--installed')},
    {'cmd': ('dnf', 'list', 'installed'), 'skew': 1},
    {'cmd': ('dpkg', '--get-selections')},
    {'cmd': ('emerge', '-ep', 'world'), 'skew': 5},
    {'cmd': ('ls', '-1', get_homebrew_cellar_path())},  # Homebrew.
    {'cmd': ('nix-env', '-q')},
    {'cmd': ('pacman', '-Q')},
    {'cmd': ('pkg_info', '-a')},
    {
        'cmd': ('pkg', '-N', 'info', '-a'),
        # Query `pkg` only on *BSD systems to avoid inconsistencies.
        'only_on': (Distributions.FREEBSD, Distributions.NETBSD, Distributions.OPENBSD)
    },
    {'cmd': ('port', 'installed'), 'skew': 1},
    {'cmd': ('rpm', '-qa')},
    {'cmd': ('ls', '-1', '/var/log/packages/')},  # SlackWare.
    {'cmd': ('yum', 'list', 'installed'), 'skew': 2},
    {'cmd': ('zypper', 'search', '-i'), 'skew': 5}
)


class Packages(Entry):
    """Relies on the first found packages manager to list the installed packages"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for packages_tool in PACKAGES_TOOLS:
            if 'only_on' in packages_tool \
                and Distributions.get_local() not in packages_tool['only_on']:
                continue

            try:
                results = check_output(
                    packages_tool['cmd'],
                    stderr=DEVNULL,
                    env={
                        'LANG': 'C',
                        # Alpine Linux: We have to manually propagate `PATH`.
                        #               `apk` wouldn't be found otherwise.
                        'PATH': os.getenv('PATH')
                    },
                    universal_newlines=True
                )
            except (FileNotFoundError, PermissionError, CalledProcessError):
                continue

            # Here we *may* use `\n` as `universal_newlines` has been set.
            if self.value:
                self.value += results.count('\n')
            else:
                self.value = results.count('\n')

            # If any, deduct output skew present due to the packages tool itself.
            if 'skew' in packages_tool:
                self.value -= packages_tool['skew']

            # For DPKG only, remove any not purged package.
            if packages_tool['cmd'][0] == 'dpkg':
                self.value -= results.count('deinstall')

            # Let's just loop over, in case there are multiple package managers.
