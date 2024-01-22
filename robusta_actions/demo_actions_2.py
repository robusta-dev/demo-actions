from kubernetes import client
from kubernetes.client import V1PodList
from typing import List, Optional

from robusta.api import *


class PodStatusParams(ActionParams):
    """
    :var status: query pods by this status
    :var name: name prefix to filter by
    """
    status: str = None
    name: str = ""


@action
def list_pods_by_status(event: ExecutionBaseEvent, params: PodStatusParams):
    logging.info("list_pods_by_status start")
    field_selector = None
    if params.status:
        field_selector = f"status.phase={params.status}"

    pods: V1PodList = client.CoreV1Api().list_pod_for_all_namespaces(field_selector=field_selector)
    filtered_pods = [pod for pod in pods.items if params.name in pod.metadata.name]
    event.add_finding(Finding(
        title=f"Pod list for status {params.status}",
        aggregation_key="Pod status report",
    ))
    if filtered_pods:
        event.add_enrichment([
            TableBlock(
                table_name="pods list",
                headers=["name", "namespace", "status"],
                rows=[[pod.metadata.name, pod.metadata.namespace, pod.status.phase] for pod in filtered_pods]
            )
        ])
    else:
        event.add_enrichment([MarkdownBlock(f"No pods with status {params.status}")])
    logging.info("list_pods_by_status done")


@action
def get_pod_events(event: PodEvent):
    pod = event.get_pod()
    block_list: List[BaseBlock] = []
    event_list: EventList = EventList.listNamespacedEvent(
        namespace=pod.metadata.namespace,
        field_selector=f"involvedObject.name={pod.metadata.name}",
    ).obj

    if event_list.items:  # add enrichment only if we got events
        block_list.append(MarkdownBlock("*Pod events:*"))
        headers = ["time", "message"]
        rows = [
            [parse_kubernetes_datetime_to_ms(event.lastTimestamp), event.message]
            for event in event_list.items
        ]
        block_list.append(
            TableBlock(
                rows=rows,
                headers=headers,
                column_renderers={"time": RendererType.DATETIME},
            )
        )
        event.add_enrichment(block_list)
    else:
        event.add_enrichment([MarkdownBlock(f"No events found for pod {pod.metadata.name} namespace {pod.metadata.namespace}")])

@action
def my_demo_action(event: ExecutionBaseEvent):
    msg = "demo action v4"
    logging.info(msg)
    event.add_enrichment([MarkdownBlock(msg)])


class StatusSilenceParams(ActionParams):
    """
    :var include: If available, will stop processing unless the pod status is in the include list
    :var exclude: If available, will stop processing if the pod status is in the exclude list

    :example include: ["Pending"]
    :example exclude: ["Evicted"]
    """

    include: Optional[List[str]]
    exclude: Optional[List[str]]


@action
def pod_status_silence(event: PodEvent, params: StatusSilenceParams):
    """
    Stop execution based on pod statuses.
    """
    pod = event.get_pod()
    if not pod:
        logging.info("Cannot run pod_status_silence with no pod. skipping")
        return

    if params.include:  # Stop unless pod status in include list
        if pod.status.phase not in params.include:
            event.stop_processing = True
            return

    if params.exclude:
        if pod.status.phase in params.exclude:
            event.stop_processing = True


@action
def job_deletion(event: JobEvent):
    """
    Delete the job from the cluster
    """
    job = event.get_job()
    if not job:
        logging.info("Cannot run job_deletion with no job. skipping")
        return

    # After deletion the metadata is empty. Saving the name and namespace
    name = job.metadata.name
    namespace = job.metadata.namespace
    job.delete()
    event.add_enrichment([MarkdownBlock(f"Job *{namespace}/{name}* deleted")])

@action
def pod_evicted_notification(event: PodChangeEvent):
    if event.operation == K8sOperationType.UPDATE:  # check only for existing pods, not updates or deletes
        old_phase = event.old_obj.status.phase
        new_phase = event.obj.status.phase

        if old_phase != 'Evicted' and new_phase == 'Evicted':
            event.add_finding(Finding(
                title=f"Pod {event.obj.metadata.name}/{event.obj.metadata.namespace} evicted",
                aggregation_key="PodEvicted",
            ))