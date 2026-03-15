import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import * as api from "@/lib/api";
import { InjectModal } from "./InjectModal";

export function SimulationDashboard() {
  const { data: status } = useQuery({
    queryKey: ["simulation-status"],
    queryFn: api.fetchSimulationStatus,
  });

  const [tickMinutes, setTickMinutes] = useState(30);
  const [injectOpen, setInjectOpen] = useState(false);

  const currentStatus = status?.status ?? "stopped";

  const handleStart = () => api.startSimulation();
  const handlePause = () => api.pauseSimulation();
  const handleReset = () => api.resetSimulation();
  const handleTickChange = (val: number | readonly number[]) => {
    const v = Array.isArray(val) ? val[0] : val;
    setTickMinutes(v);
    api.updateTickInterval(v);
  };

  return (
    <div>
      <h2 className="mb-4 text-lg font-semibold">Simulation Controls</h2>

      {/* Stat cards */}
      <div className="mb-6 grid grid-cols-2 gap-4">
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
              Tick Interval
            </CardTitle>
          </CardHeader>
          <CardContent>
            <span className="text-lg font-semibold">{tickMinutes} min</span>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Issues in Flight
            </CardTitle>
          </CardHeader>
          <CardContent>
            <span className="text-lg font-semibold">0</span>
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
              N/A
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
      <div className="max-w-sm">
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

      <InjectModal open={injectOpen} onClose={() => setInjectOpen(false)} />
    </div>
  );
}
