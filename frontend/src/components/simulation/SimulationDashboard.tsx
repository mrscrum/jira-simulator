import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import * as api from "@/lib/api";
import { InjectModal } from "./InjectModal";

export function SimulationDashboard() {
  const queryClient = useQueryClient();

  const { data: status } = useQuery({
    queryKey: ["simulation-status"],
    queryFn: api.fetchSimulationStatus,
    refetchInterval: 5000,
  });

  const { data: clockData } = useQuery({
    queryKey: ["simulation-clock"],
    queryFn: api.fetchClockSpeed,
  });

  const [tickMinutes, setTickMinutes] = useState(30);
  const [injectOpen, setInjectOpen] = useState(false);

  const currentStatus = status?.status ?? "stopped";
  const tickCount = status?.tick_count ?? 0;
  const lastTick = status?.last_successful_tick ?? null;
  const clockSpeed = clockData?.speed ?? 1;

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
              Last Tick
            </CardTitle>
          </CardHeader>
          <CardContent>
            <span className="text-lg font-semibold text-muted-foreground">
              {lastTick ? new Date(lastTick).toLocaleTimeString() : "N/A"}
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
          onClick={() => setInjectOpen(true)}
          data-testid="sim-inject-btn"
        >
          Inject Dysfunction
        </Button>
      </div>

      {/* Tick interval slider */}
      <div className="mb-4 max-w-sm">
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

      {/* Clock speed slider */}
      <div className="max-w-sm">
        <label className="mb-2 block text-sm font-medium">
          Clock Speed: {clockSpeed}x
          {clockSpeed > 1 && (
            <span className="ml-2 text-xs text-amber-600">
              (accelerated — testing mode)
            </span>
          )}
        </label>
        <Slider
          value={[clockSpeed]}
          onValueChange={handleSpeedChange}
          min={1}
          max={120}
          step={1}
          data-testid="clock-slider"
        />
      </div>

      <InjectModal open={injectOpen} onClose={() => setInjectOpen(false)} />
    </div>
  );
}
