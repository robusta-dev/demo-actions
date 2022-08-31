from robusta.api import *
from kubernetes import client


class KindYamlParams(ActionParams):
    """
    :var kind: k8s requested kind. One of: deployments/replicasets/daemonsets/statefulsets
    """
    kind: str


@action
def get_kind_yamls(event: ExecutionBaseEvent, params: KindYamlParams):
    k8s_client = client.ApiClient()

    response = k8s_client.call_api(
        resource_path=f"/apis/apps/v1/{params.kind}",
        method="GET",  auth_settings=['BearerToken'], _preload_content=False, _return_http_data_only=True
    )
    event.add_finding(Finding(
        title=f"Cluster {params.kind} manifests report",
        aggregation_key="Manifest report",
    ))
    event.add_enrichment([FileBlock(f"{params.kind}.yaml", yaml.dump(json.loads(response.data)).encode())])


class FindingTemplatedOverrides(ActionParams):
    """
    :var title: Overriding finding title.
    :var description: Overriding finding description.
    :var severity: Overriding finding severity. Allowed values: DEBUG, INFO, LOW, MEDIUM, HIGH
    :example severity: DEBUG
    """

    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None


@action
def templated_customise_finding(event: ExecutionBaseEvent, params: FindingTemplatedOverrides):
    """
    Overrides a finding attribute with the provided value.

    All messages from Robusta are represented as a Finding object.
    This action lets you override Finding fields to change that messages Robusta sends.
    This lets you modify messages created by other actions without needing to rewrite those actions.

    This action does not create a new Finding, it just overrides the attributes of an existing Finding.
    It must be placed as the last action in the playbook configuration, to override the attributes created by previous
    actions
    """
    severity: Optional[FindingSeverity] = (
        FindingSeverity[params.severity] if params.severity else None
    )
    subject = event.get_subject()
    labels = defaultdict(lambda: "<missing>")
    labels.update({
        "name": subject.name,
        "kind": subject.subject_type,
        "namespace": subject.namespace if subject.namespace else "<missing>",
        "node": subject.node if subject.node else "<missing>",
    })

    title: str = Template(params.title).safe_substitute(labels)
    description: str = Template(params.description).safe_substitute(labels) if params.description else None

    event.override_finding_attributes(title, description, severity)
