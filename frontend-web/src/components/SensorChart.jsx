import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceLine, ResponsiveContainer, Legend,
} from 'recharts';

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-surface border border-surface-border rounded-xl px-4 py-3 shadow-lg text-[12px]">
      <p className="font-semibold text-on-surface-variant mb-2">{label}</p>
      {payload.map(p => (
        <div key={p.name} className="flex items-center gap-2 mb-1">
          <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: p.color }} />
          <span className="text-on-surface-variant">{p.name}:</span>
          <span className="font-bold text-on-surface">{p.value}{p.name.includes('Accel') || p.name.includes('Baseline') || p.name.includes('Threshold') ? 'g' : ''}</span>
        </div>
      ))}
    </div>
  );
};

export default function SensorChart({ data, crashIndex = 20 }) {
  const crashLabel = data?.[crashIndex]?.label;

  return (
    <div className="w-full h-[280px]">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 10, right: 16, left: -10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e1e2ee" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 10, fill: '#727687' }}
            tickLine={false}
            axisLine={false}
            interval={4}
          />
          <YAxis
            tick={{ fontSize: 10, fill: '#727687' }}
            tickLine={false}
            axisLine={false}
            domain={[0, 12]}
            label={{ value: 'g / rad·s⁻¹', angle: -90, position: 'insideLeft', style: { fontSize: 9, fill: '#727687' }, dy: 50 }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            iconType="circle"
            iconSize={8}
            wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
          />

          {/* Rolling baseline */}
          <Line
            type="monotone"
            dataKey="baseline"
            name="Baseline"
            stroke="#727687"
            strokeDasharray="4 4"
            strokeWidth={1.5}
            dot={false}
            activeDot={false}
          />

          {/* Crash threshold */}
          <Line
            type="monotone"
            dataKey="threshold"
            name="Threshold"
            stroke="#EF4444"
            strokeDasharray="6 3"
            strokeWidth={1.5}
            dot={false}
            activeDot={false}
          />

          {/* Gyroscope */}
          <Line
            type="monotone"
            dataKey="gyro"
            name="Gyro Mag."
            stroke="#8b5cf6"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, strokeWidth: 0 }}
          />

          {/* Acceleration */}
          <Line
            type="monotone"
            dataKey="accel"
            name="Accel Mag."
            stroke="#0050cb"
            strokeWidth={2.5}
            dot={false}
            activeDot={{ r: 5, strokeWidth: 0 }}
          />

          {/* Crash event marker */}
          {crashLabel && (
            <ReferenceLine
              x={crashLabel}
              stroke="#EF4444"
              strokeWidth={2}
              strokeDasharray="0"
              label={{ value: '⚡ Crash', position: 'top', fill: '#EF4444', fontSize: 11, fontWeight: 700 }}
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
