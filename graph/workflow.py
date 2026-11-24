import json
from pathlib import Path
from typing import Any, Dict, List, TypedDict

from langgraph.graph import END, StateGraph

from agents.crawler_agent import crawl_website
from agents.test_generator_agent import generate_test_cases


class WorkflowState(TypedDict):
    url: str
    pages: List[Dict[str, Any]]
    test_cases: List[Dict[str, Any]]
    report: Dict[str, Any]


async def crawl_node(state: WorkflowState) -> WorkflowState:
    pages = await crawl_website(state["url"])
    state["pages"] = pages
    return state


def generate_node(state: WorkflowState) -> WorkflowState:
    state["test_cases"] = generate_test_cases(state.get("pages", []))
    return state


def report_node(state: WorkflowState) -> WorkflowState:
    pages = state.get("pages", [])
    test_cases = state.get("test_cases", [])

    summary = {
        "input_url": state.get("url", ""),
        "pages_crawled": len(pages),
        "test_cases_generated": len(test_cases),
        "page_urls": [p.get("url", "") for p in pages],
    }

    print("\nFinal summary:")
    print(f"  Pages crawled: {summary['pages_crawled']}")
    print(f"  Test cases generated: {summary['test_cases_generated']}")

    state["report"] = summary

    reports_dir = Path(__file__).resolve().parent.parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    output_path = reports_dir / "final_report.json"
    output_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

    return state


def build_workflow():
    graph = StateGraph(WorkflowState)
    graph.add_node("crawl_node", crawl_node)
    graph.add_node("generate_node", generate_node)
    graph.add_node("report_node", report_node)

    graph.set_entry_point("crawl_node")
    graph.add_edge("crawl_node", "generate_node")
    graph.add_edge("generate_node", "report_node")
    graph.add_edge("report_node", END)

    return graph.compile()

