"""Fresh exact-identity resource observations; no signals, clock or PID scan.

The trusted caller supplies its ORIGINAL clock-only checkpoint.  This object
never advances that caller's last-successful-sample timestamp.  Departed known
identities remain provenance, and are not represented as a live RSS of zero.
"""
import math
import psutil


class ResourceSamplingError(RuntimeError):
    def __init__(self, receipt):
        self.receipt = receipt
        super().__init__(receipt['code'])


class VerifiedResourceSampler:
    def __init__(self, process_factory=None):
        self.process_factory = psutil.Process if process_factory is None else process_factory
        self.known = set()
        self.departed = []
        self.failure = None
        self.successful_rounds = 0
        self.last_receipt = None
        if not callable(self.process_factory):
            self._stop('resource_process_factory_required')

    def _stop(self, code, identity=None, action=None, error=None):
        receipt = dict(code=code, action=action,
                       identity=list(identity) if identity is not None else None,
                       exception_type=type(error).__name__ if error is not None else None)
        self.failure = ResourceSamplingError(receipt)
        raise self.failure from error

    def _check(self, checkpoint):
        if self.failure is not None:
            raise self.failure
        if not callable(checkpoint):
            self._stop('resource_checkpoint_required')
        try:
            checkpoint()
        except BaseException as error:
            self.failure = error
            raise

    def _identity(self, value):
        if (type(value) not in (tuple, list) or len(value) != 2
                or type(value[0]) is not int or value[0] <= 0
                or type(value[1]) not in (int, float)
                or not math.isfinite(value[1]) or value[1] <= 0):
            self._stop('resource_typed_known_identity_required')
        return value[0], float(value[1])

    def remember(self, identities):
        if self.failure is not None:
            raise self.failure
        if type(identities) not in (tuple, list, set, frozenset, dict) or len(identities) > 30000:
            self._stop('resource_typed_known_inventory_required')
        for value in identities:
            self.known.add(self._identity(value))
        if len(self.known) > 30000:
            self._stop('resource_known_inventory_over_bound')

    def _call(self, identity, action, operation, checkpoint):
        self._check(checkpoint)
        try:
            value = operation()
        except psutil.NoSuchProcess:
            self._check(checkpoint)
            raise
        except BaseException as error:
            self._stop('resource_observation_unconfirmed', identity, action, error)
        self._check(checkpoint)
        return value

    def _fresh(self, identity, checkpoint):
        process = self._call(identity, 'open_fresh_PID',
                             lambda: self.process_factory(identity[0]), checkpoint)
        observed = self._call(identity, 'fresh_birth',
                              lambda: (process.pid, process.create_time()), checkpoint)
        actual = self._identity(observed)
        if actual[0] != identity[0]:
            self._stop('resource_fresh_PID_mismatch', identity)
        return process, actual[1]

    def _record_departed(self, identity, reason, replacement_birth=None):
        row = dict(pid=identity[0], create_time=identity[1], state=reason,
                   replacement_create_time=replacement_birth, rss_bytes=None)
        if row not in self.departed:
            self.departed.append(row)
        return row

    def confirm_departed(self, identity, *, checkpoint):
        """A NEW PID lookup must prove this exact known identity gone/reused."""
        self._check(checkpoint)
        identity = self._identity(identity)
        self.remember([identity])
        try:
            unused_process, birth = self._fresh(identity, checkpoint)
        except psutil.NoSuchProcess:
            return self._record_departed(identity, 'fresh_confirmed_absent')
        if birth != identity[1]:
            return self._record_departed(identity, 'fresh_confirmed_reused', birth)
        self._stop('resource_same_identity_still_present', identity,
                   'confirm_after_NoSuchProcess')

    def discover_owned_tree(self, root_identity, *, checkpoint):
        """Bounded traversal of one supplied owned root, never process_iter.

        Discovery cannot manufacture an unknown child's birth.  A novel child
        is remembered only while the original root is freshly stable around
        traversal; uncertainty about a new identity is a fatal observation.
        """
        self._check(checkpoint)
        root_identity = self._identity(root_identity)
        self.remember([root_identity])
        tentative = []
        try:
            process, birth = self._fresh(root_identity, checkpoint)
            if birth != root_identity[1]:
                self._record_departed(root_identity, 'fresh_confirmed_reused', birth)
                return
            children = self._call(root_identity, 'owned_descendant_traversal',
                                  lambda: process.children(recursive=True), checkpoint)
            if type(children) not in (list, tuple):
                self._stop('resource_descendant_inventory_untyped', root_identity)
            for child in children:
                try:
                    value = self._call(root_identity, 'owned_child_birth',
                                       lambda: (child.pid, child.create_time()), checkpoint)
                except psutil.NoSuchProcess as error:
                    self._stop('resource_discovered_birth_unverified', root_identity,
                               'owned_child_birth', error)
                tentative.append(self._identity(value))
            unused_process, after_birth = self._fresh(root_identity, checkpoint)
            if after_birth != root_identity[1]:
                if any(identity not in self.known for identity in tentative):
                    self._stop('resource_new_descendants_scope_unconfirmed', root_identity)
                self._record_departed(root_identity, 'fresh_confirmed_reused', after_birth)
                return
        except psutil.NoSuchProcess:
            if any(identity not in self.known for identity in tentative):
                self._stop('resource_new_descendants_scope_unconfirmed', root_identity)
            self.confirm_departed(root_identity, checkpoint=checkpoint)
            return
        self.remember(tentative)

    def sample(self, identities, *, required=(), checkpoint):
        self._check(checkpoint)
        self.remember(identities)
        if type(required) not in (tuple, list, set, frozenset, dict):
            self._stop('resource_typed_required_inventory_required')
        requested = {self._identity(value) for value in identities}
        required = {self._identity(value) for value in required}
        if not required:
            self._stop('resource_mandatory_identity_required')
        if not required <= requested:
            self._stop('resource_required_identity_not_requested')
        sampled, departed = [], []
        for identity in sorted(requested):
            try:
                process, birth = self._fresh(identity, checkpoint)
                if birth != identity[1]:
                    departed.append(self._record_departed(identity, 'fresh_confirmed_reused', birth))
                    continue
                rss = self._call(identity, 'memory_info',
                                 lambda: process.memory_info().rss, checkpoint)
                if type(rss) is not int or rss < 0:
                    self._stop('resource_RSS_untyped_or_negative', identity)
                unused_process, after_birth = self._fresh(identity, checkpoint)
                if after_birth != identity[1]:
                    departed.append(self._record_departed(identity, 'fresh_confirmed_reused', after_birth))
                    continue
                sampled.append(dict(pid=identity[0], create_time=identity[1], rss_bytes=rss))
            except psutil.NoSuchProcess:
                departed.append(self.confirm_departed(identity, checkpoint=checkpoint))
        sampled_ids = {(row['pid'], row['create_time']) for row in sampled}
        if not required <= sampled_ids:
            self._stop('resource_mandatory_identity_not_sampled')
        self._check(checkpoint)
        receipt = dict(schema='verified-known-resource-sample-v1',
                       sampled=sampled, departed=departed,
                       sampled_count=len(sampled), required_count=len(required),
                       known_count=len(self.known),
                       scope='sampled_stable_known_RSS_not_OS_lifetime_peak')
        self.successful_rounds += 1
        self.last_receipt = receipt
        return receipt
