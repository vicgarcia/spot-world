import logging
from bosdyn.client.lease import LeaseKeepAlive, LeaseClient, ResourceAlreadyClaimedError

logger = logging.getLogger(__name__)


class LeaseError(Exception):
    pass


class LeaseStatus:
    NONE = 'NONE'
    ACTIVE = 'ACTIVE'


class LeaseFacade:

    def __init__(self, spot):
        self._spot = spot
        self._lease = None
        self._keepalive = None

    @property
    def client(self):
        return self._spot._robot.ensure_client(LeaseClient.default_service_name)

    @property
    def status(self):
        if self._lease is not None:
            return LeaseStatus.ACTIVE
        LeaseStatus.NONE

    @property
    def current(self):
        return self._lease

    def acquire(self):
        # todo: handle already having a lease? throw our own LeaseError?
        if not self._lease:
            try:
                self._lease = self.client.acquire()
                self._keepalive = LeaseKeepAlive(self.client)
            except ResourceAlreadyClaimedError:
                raise LeaseError('unable to acquire lease, robot is already being controlled')

    def take(self):
        if not self._lease:
            self._lease = self.client.take()
            self._keepalive = LeaseKeepAlive(self.client)

    def release(self):
        # todo: handle not having a lease?
        if self._lease:
            self.client.return_lease(self._lease)
            self._keepalive.shutdown()
            self._lease = None
            self._keepalive = None
