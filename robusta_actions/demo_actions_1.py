from robusta.api import *
from kubernetes import client
from kubernetes.client import V1DeploymentList, V1DaemonSetList, V1PodList, V1StatefulSetList, V1ReplicaSetList


@action
def echo_test(event: ExecutionBaseEvent):
    print("echo test v8")
    

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


@action
def print_cluster_resources(event: ExecutionBaseEvent):
    logging.info("Printing visible cluster resources")
    try:
        deployments: V1DeploymentList = client.AppsV1Api().list_deployment_for_all_namespaces()
        logging.info("Deployments:")
        for deployment in deployments.items:
            logging.info(f"Deployment: name: {deployment.metadata.name} namespace: {deployment.metadata.namespace}")

        statefulsets: V1StatefulSetList = client.AppsV1Api().list_stateful_set_for_all_namespaces()
        logging.info("Statefulsets:")
        for stat in statefulsets.items:
            logging.info(f"StatefulSet: name: {stat.metadata.name} namespace: {stat.metadata.namespace}")

        daemonsets: V1DaemonSetList = client.AppsV1Api().list_daemon_set_for_all_namespaces()
        logging.info("DaemonSets:")
        for ds in daemonsets.items:
            logging.info(f"DaemonSet: name: {ds.metadata.name} namespace: {ds.metadata.namespace}")

        replicasets: V1ReplicaSetList = client.AppsV1Api().list_replica_set_for_all_namespaces()
        logging.info("ReplicaSets:")
        for rs in replicasets.items:
            logging.info(f"ReplicaSet: name: {rs.metadata.name} namespace: {rs.metadata.namespace}")

        pods: V1PodList = client.CoreV1Api().list_pod_for_all_namespaces()
        logging.info("Pods:")
        for pod in pods.items:
            logging.info(f"Pod: name: {pod.metadata.name} namespace: {pod.metadata.namespace}")

    except Exception:
        logging.error(
            f"Failed to visible cluster resources",
            exc_info=True,
        )

class FindingFields(ActionParams):
    """
    :var title: Finding title. Title can be templated with name/namespace/kind/node of the resource, if applicable
    :var aggregation_key: Identifier of this finding
    :var description: Finding description. Description can be templated
    :var severity: Finding severity. Allowed values: DEBUG, INFO, LOW, MEDIUM, HIGH

    :example title: "Job $name on namespace $namespace failed"
    :example aggregation_key: "Job Failure"
    :example severity: DEBUG
    """

    title: str
    aggregation_key: str
    description: Optional[str] = None
    severity: Optional[str] = "HIGH"


@action
def create_finding_demo(event: ExecutionBaseEvent, params: FindingFields):
    """
    Create a new finding.

    All messages from Robusta are represented as a Finding object.

    This action creates a Finding that Robusta sends, with the specified fields.

    """
    logging.info(f"create_finding_demo {params}")
    subject = event.get_subject()
    labels = defaultdict(lambda: "<missing>")
    labels.update({
        "name": subject.name,
        "kind": subject.subject_type,
        "namespace": subject.namespace if subject.namespace else "<missing>",
        "node": subject.node if subject.node else "<missing>",
    })

    event.add_finding(Finding(
        title=Template(params.title).safe_substitute(labels),
        description=Template(params.description).safe_substitute(labels) if params.description else None,
        aggregation_key=params.aggregation_key,
        severity=FindingSeverity.from_severity(params.severity),
        source=event.get_source(),
        subject=event.get_subject(),
    ))
