import pytest
from agent_os.learning.optimizer import PerformanceOptimizer

def test_performance_optimizer_metrics_and_warnings():
    optimizer = PerformanceOptimizer()

    # Track metrics within healthy limits
    optimizer.track_metric("prompt_size", 4000)
    optimizer.track_metric("latency", 1.5)
    optimizer.track_metric("success_rate", 1.0)
    optimizer.track_metric("retry_count", 0)

    # Recommendations should be empty since everything is healthy
    recs = optimizer.get_recommendations()
    assert len(recs) == 0

    # Track metrics exceeding warning limits
    optimizer.track_metric("prompt_size", 16000) # Average will be (4000+16000)/2 = 10000 -> warning
    optimizer.track_metric("prompt_size", 12000) # Average is now (4000+16000+12000)/3 = 10666.7 > 10000
    optimizer.track_metric("latency", 9.0) # Average is now (1.5+9.0)/2 = 5.25s > 5s
    optimizer.track_metric("success_rate", 0.0) # Average is now (1.0+0.0)/2 = 50.0% < 70%
    optimizer.track_metric("retry_count", 3.0) # Average is now (0.0+3.0)/2 = 1.5 > 1.0

    recs_warning = optimizer.get_recommendations()
    assert len(recs_warning) >= 4
    
    # Verify metric warning keys exist
    metrics_flagged = {r["metric"] for r in recs_warning}
    assert "Prompt Size" in metrics_flagged
    assert "Latency" in metrics_flagged
    assert "Success Rate" in metrics_flagged
    assert "Retry Count" in metrics_flagged

def test_performance_optimizer_report_generation():
    optimizer = PerformanceOptimizer()
    optimizer.track_metric("prompt_size", 12000)
    
    report = optimizer.generate_report()
    assert "# Performance Metrics Report" in report
    assert "| Prompt Size |" in report
    assert "Optimization Recommendations" in report
