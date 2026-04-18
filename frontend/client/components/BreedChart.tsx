export function BreedChart() {
  const breeds = [
    { name: "Chihuahua", color: "#06B6D4", hours: 55 },
    { name: "Pug", color: "#FBBF24", hours: 45 },
    { name: "French Bulldog", color: "#FCD34D", hours: 50 },
    { name: "Beagle", color: "#60A5FA", hours: 65 },
    { name: "Bulldog", color: "#A78BFA", hours: 40 },
    { name: "Poodle", color: "#EC4899", hours: 75 },
    { name: "Labrador", color: "#F87171", hours: 80 },
    { name: "German Shepherd", color: "#34D399", hours: 85 },
    { name: "Boxer", color: "#38BDF8", hours: 70 },
    { name: "Labrador Retriever", color: "#06B6D4", hours: 80 },
  ];

  const maxHours = 100;

  return (
    <div className="mb-8">
      <div className="flex flex-col lg:flex-row gap-8">
        {/* Chart */}
        <div className="flex-1">
          <div className="flex items-flex-end justify-between h-80 gap-3 p-6 bg-secondary/50 rounded-xl">
            {breeds.slice(0, 9).map((breed) => (
              <div key={breed.name} className="flex flex-col items-center flex-1 gap-2">
                <div className="flex-1 w-full flex items-flex-end justify-center">
                  <div
                    className="w-8 rounded-full transition-all duration-300 hover:opacity-80 shadow-sm"
                    style={{
                      height: `${(breed.hours / maxHours) * 100}%`,
                      backgroundColor: breed.color,
                      minHeight: "4px",
                    }}
                  />
                </div>
                <span className="text-xs text-muted-foreground text-center font-medium">
                  {breed.hours}m
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Legend */}
        <div className="grid grid-cols-2 gap-4 h-fit">
          {breeds.map((breed) => (
            <div key={breed.name} className="flex items-center gap-2">
              <div
                className="w-3 h-3 rounded-full flex-shrink-0"
                style={{ backgroundColor: breed.color }}
              />
              <span className="text-xs text-muted-foreground">{breed.name}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
