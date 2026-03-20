import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import * as api from "@/lib/api";
import type { SimulationStatus, TeamSprintStatus } from "@/lib/types";

export function SimulationDashboard() {
  const queryClient = useQueryClient();

  const { data: status } = useQuery<SimulationStatus>({
    queryKey: ["simulation-status"],
    queryFn: api.fetchSimulationStatus,
    refetchInterval: 5000,
  });

  const { data: clockData } = useQuery({
    queryKey: ["simulation-clock"],
    queryFn: api.fetchClockSpeed,
  });

  const [tickMinutes, setTickMinutes] = useState(30);
  const [tickResult, setTickResult] = useState<string | null>(null);

  const currentStatus = status?.status ?? "stopped";
  const tickCount = status?.tick_count ?? 0;
  const lastTick = status?.last_successful_tick ?? null;
  const clockSpeed = clockData?.speed ?? 1;
  const simTime = status?.sim_time ?? null;
  const teams: TeamSprintStatus[] = status?.teams ?? [];

  const refreshStatus = () =>
    queryClient.invalidateQueries({ queryKey: ["simulation-status"] });

  const handleStart = async () => {
    await api.startSimulation();
    refreshStatus();
  };
  const handlePause = async () => {
    await api.pauseSimulation();
    refreshStatus();
  };
  const handleReset = async () => {
    await api.resetSimulation();
    refreshStatus();
  };
  const handleManualTick = async () => {
    setTickResult("Running...");
    try {
      const result = await api.triggerManualTick();
      setTickResult(`Tick #${(result as Record<string, unknown>).tick_count} completed`);
      refreshStatus();
    } catch (e) {
      setTickResult(`Error: ${e instanceof Error ? e.message : String(e)}`);
    }
  };
  const handleTickChange = (val: number | readonly number[]) => {
    const v = Array.isArray(val) ? val[0] : val;
    setTickMinutes(v);
    api.updateTickInterval(v);
  };
  const handleSpeedChange = async (val: number | readonly number[]) => {
    const v = Array.isArray(val) ? val[0] : val;
    await api.setClockSpeed(v);
    queryClient.invalidateQueries({ queryKey: ["simulation-clock"] });
  };

  // Suppress unused variable warning
  void lastTick;

  return (
    <div>
      <h2 className="mb-4 text-lg font-semibold">Simulation Controls</h2>

      {/* Stat cards */}
      <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Status
            </CardTitle>
          </CardHeader>
          <CardContent>
            <span
              className="text-lg font-semibold capitalize"
              data-testid="sim-status"
            >
              {currentStatus}
            </span>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Tick Count
            </CardTitle>
          </CardHeader>
          <CardContent>
            <span className="text-lg font-semibold">{tickCount}</span>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Clock Speed
            </CardTitle>
          </CardHeader>
          <CardContent>
            <span className="text-lg font-semibold">{clockSpeed}x</span>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Sim Time
            </CardTitle>
          </CardHeader>
          <CardContent>
            <span className="text-sm font-semibold text-muted-foreground">
              {simTime ? new Date(simTime).toLocaleString() : "N/A"}
            </span>
          </CardContent>
        </Card>
      </div>

      {/* Controls */}
      <div className="mb-6 flex items-center gap-2">
        <Button
          onClick={currentStatus === "running" ? handlePause : handleStart}
          data-testid="sim-toggle-btn"
        >
          {currentStatus === "running" ? "Pause" : "Start"}
        </Button>
        <Button
          variant="outline"
          onClick={handleReset}
          data-testid="sim-reset-btn"
        >
          Reset
        </Button>
        <Button
          variant="outline"
          onClick={handleManualTick}
          data-testid="sim-tick-btn"
        >
          Manual Tick
        </Button>
        {tickResult && (
          <span className="text-sm text-muted-foreground">{tickResult}</span>
        )}
      </div>

      {/* Sliders */}
      <div className="mb-6 grid grid-cols-2 gap-8 max-w-2xl">
        <div>
          <label className="mb-2 block text-sm font-medium">
            Tick Interval: {tickMinutes} min
          </label>
          <Slider
            value={[tickMinutes]}
            onValueChange={handleTickChange}
            min={5}
            max={120}
            step={5}
            data-testid="tick-slider"
          />
        </div>
        <div>
          <label className="mb-2 block text-sm font-medium">
            Clock Speed: {clockSpeed}x
            {clockSpeed > 1 && (
              <span className="ml-2 text-xs text-amber-600">
                (accelerated)
              </span>
            )}
          </label>
          <Slider
            value={[clockSpeed]}
            onValueChange={handleSpeedChange}
            min={1}
            max={3600}
            step={1}
            data-testid="clock-slider"
          />
        </div>
      </div>

      {/* Per-team sprint status */}
      {teams.length > 0 && (
        <div>
          <h3 className="mb-3 text-base font-semibold">Team Sprints</h3>
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {teams.map((t) => (
              <Card key={t.team_id}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium">
                    {t.team_name}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">
                      Sprint #{t.sprint_number}
                    </span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        t.phase === "ACTIVE"
                          ? "bg-green-100 text-green-700"
                          : t.phase === "COMPLETED"
                            ? "bg-blue-100 text-blue-700"
                            : "bg-amber-100 text-amber-700"
                      }`}
                    >
                      {t.phase ?? "—"}
                    </span>
                  </div>
                  <div className="text-sm">
                    <span className="font-medium">{t.completed_points}</span>
                    <span className="text-muted-foreground">
                      {" "}/ {t.committed_points} SP
                    </span>
                  </div>
                  {t.committed_points > 0 && (
                    <div className="h-2 rounded-full bg-muted">
                      <div
                        className="h-2 rounded-full bg-primary transition-all"
                        style={{
                          width: `${Math.min(100, (t.completed_points / t.committed_points) * 100)}%`,
                        }}
                      />
                    </div>
                  )}
                  <div className="text-xs text-muted-foreground">
                    {t.total_sprints} total sprints
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
