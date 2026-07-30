from typing import Any, Dict, List
from agent_os.learning.interfaces import IPerformanceOptimizer

class PerformanceOptimizer(IPerformanceOptimizer):
    """Performance Optimizer tracking runtime metrics and recommending configurations."""
    
    def __init__(self) -> None:
        self._metrics: Dict[str, List[float]] = {
            "prompt_size": [],
            "latency": [],
            "success_rate": [],
            "retry_count": [],
            "cache_hits": [],
            "indexing_time": [],
            "context_accuracy": []
        }

    def track_metric(self, name: str, value: float) -> None:
        name_key = name.lower().replace(" ", "_")
        if name_key in self._metrics:
            self._metrics[name_key].append(value)

    def _avg(self, key: str) -> float:
        vals = self._metrics.get(key, [])
        return sum(vals) / len(vals) if vals else 0.0

    def get_recommendations(self) -> List[Dict[str, Any]]:
        recommendations = []

        # 1. Prompt Size Warning
        avg_prompt_size = self._avg("prompt_size")
        if avg_prompt_size > 10000:
            recommendations.append({
                "metric": "Prompt Size",
                "status": "Warning",
                "value": f"{avg_prompt_size:.1f} tokens",
                "recommendation": "Reduce token budget in Context Virtual Memory, demote cold context faster, or omit redundant symbol signatures."
            })

        # 2. High Latency Warning
        avg_latency = self._avg("latency")
        if avg_latency > 5.0:
            recommendations.append({
                "metric": "Latency",
                "status": "Warning",
                "value": f"{avg_latency:.2f}s",
                "recommendation": "Switch default router fallback to Groq/Ollama for faster completions, or exclude target output logs."
            })

        # 3. Success Rate Warning
        if self._metrics.get("success_rate"):
            avg_success = self._avg("success_rate")
            if avg_success < 0.70:
                recommendations.append({
                    "metric": "Success Rate",
                    "status": "Critical",
                    "value": f"{avg_success * 100:.1f}%",
                    "recommendation": "Refine prompt templates, enforce more granular plans, or add safety validation assertions before committing."
                })

        # 4. Retry Count Warning
        avg_retries = self._avg("retry_count")
        if avg_retries > 1.0:
            recommendations.append({
                "metric": "Retry Count",
                "status": "Warning",
                "value": f"{avg_retries:.1f}",
                "recommendation": "Upstream model providers are rate-limiting. Enable sliding RPM window restrictions or configure Ollama local fallback."
            })

        # 5. Cache Hit rate Warning
        if self._metrics.get("cache_hits"):
            avg_hits = self._avg("cache_hits")
            if avg_hits < 0.50:
                recommendations.append({
                    "metric": "Cache Hit Rate",
                    "status": "Info",
                    "value": f"{avg_hits * 100:.1f}%",
                    "recommendation": "Increase warm memory pool size or pre-load neighbor file imports during repository scans."
                })

        # 6. Repository Indexing Time Warning
        avg_indexing = self._avg("indexing_time")
        if avg_indexing > 2.0:
            recommendations.append({
                "metric": "Repository Indexing Time",
                "status": "Warning",
                "value": f"{avg_indexing:.2f}s",
                "recommendation": "Add node_modules or output build artifacts to scan ignore list to skip parsing non-source files."
            })

        # 7. Context Accuracy Warning
        if self._metrics.get("context_accuracy"):
            avg_acc = self._avg("context_accuracy")
            if avg_acc < 0.60:
                recommendations.append({
                    "metric": "Context Accuracy",
                    "status": "Warning",
                    "value": f"{avg_acc * 100:.1f}%",
                    "recommendation": "Improve keyword similarity scoring index or load closer dependency import neighbors."
                })

        return recommendations

    def generate_report(self) -> str:
        recs = self.get_recommendations()
        
        # Build metrics summary table
        report = [
            "# Performance Metrics Report",
            "",
            "| Metric | Average Value | Tracked Count |",
            "|---|---|---|",
            f"| Prompt Size | {self._avg('prompt_size'):.1f} tokens | {len(self._metrics['prompt_size'])} |",
            f"| Latency | {self._avg('latency'):.2f}s | {len(self._metrics['latency'])} |",
            f"| Success Rate | {self._avg('success_rate') * 100:.1f}% | {len(self._metrics['success_rate'])} |",
            f"| Retry Count | {self._avg('retry_count'):.1f} | {len(self._metrics['retry_count'])} |",
            f"| Cache Hits | {self._avg('cache_hits'):.1f} | {len(self._metrics['cache_hits'])} |",
            f"| Repository Indexing | {self._avg('indexing_time'):.2f}s | {len(self._metrics['indexing_time'])} |",
            f"| Context Accuracy | {self._avg('context_accuracy') * 100:.1f}% | {len(self._metrics['context_accuracy'])} |",
            ""
        ]

        if recs:
            report.append("## Optimization Recommendations")
            report.append("")
            for r in recs:
                report.append(f"### [{r['status']}] {r['metric']} (Value: {r['value']})")
                report.append(f"> **Suggestion**: {r['recommendation']}")
                report.append("")
        else:
            report.append("## Recommendations")
            report.append("System is running optimally. No corrections needed.")

        return "\n".join(report)
