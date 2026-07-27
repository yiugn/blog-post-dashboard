import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface PublishingChartProps {
  data: Array<{
    date: string;
    posts: number;
    current: boolean;
  }>;
}

const numberFormat = new Intl.NumberFormat("ko-KR");

export default function PublishingChart({ data }: PublishingChartProps) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={{ top: 5, right: 0, left: 0 }}>
        <CartesianGrid
          strokeDasharray="0"
          vertical={false}
          stroke="#e8edf3"
        />
        <XAxis
          dataKey="date"
          axisLine={false}
          tickLine={false}
          tick={{ fill: "#94a3b8", fontSize: 10 }}
          interval={1}
        />
        <YAxis
          axisLine={false}
          tickLine={false}
          tick={{ fill: "#94a3b8", fontSize: 10 }}
          width={38}
        />
        <Tooltip
          cursor={{ fill: "#f1f5f9" }}
          contentStyle={{
            border: "1px solid #e2e8f0",
            borderRadius: 12,
            boxShadow: "0 10px 25px rgba(15,23,42,.08)",
            fontSize: 12,
          }}
          formatter={(value) => [
            `${numberFormat.format(Number(value))}개`,
            "발행",
          ]}
        />
        <Bar
          dataKey="posts"
          fill="#4f7ee8"
          radius={[6, 6, 0, 0]}
          maxBarSize={24}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}
