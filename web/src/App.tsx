import { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  App as AntApp,
  Badge,
  Button,
  Card,
  Col,
  Divider,
  Flex,
  Input,
  Layout,
  List,
  Space,
  Spin,
  Statistic,
  Tag,
  Timeline,
  Typography
} from "antd";
import {
  CheckCircleOutlined,
  EditOutlined,
  SendOutlined,
  SyncOutlined
} from "@ant-design/icons";
import { createSession, sendMessage } from "./api";
import type { AgentAction, AgentEvent, AgentSession, AgentSnapshot, ChatMessage, DecisionCard, QuoteOption } from "./types";
import "./styles.css";

const { Content, Sider } = Layout;
const { Text, Title, Paragraph } = Typography;
const { TextArea } = Input;

const stageLabels: Record<string, string> = {
  requirements_review: "需求确认",
  plan_draft: "行程草案",
  budget_tradeoff: "预算取舍",
  final_confirmation: "最终确认",
  completed: "完成",
  error: "错误"
};

const starterPrompt = "上海到杭州两天亲子游，2 人，预算 3000，想去西湖和适合孩子的地方。";

export default function App() {
  const { message: toast } = AntApp.useApp();
  const [session, setSession] = useState<AgentSession | null>(null);
  const [input, setInput] = useState(starterPrompt);
  const [advice, setAdvice] = useState("");
  const [loading, setLoading] = useState(false);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const eventSourceRef = useRef<EventSource | null>(null);

  const latestSnapshot = session?.snapshots.at(-1) ?? null;
  const pendingDecision = session?.pending_decision ?? null;

  useEffect(() => {
    if (!session?.id) {
      return undefined;
    }
    eventSourceRef.current?.close();
    const source = new EventSource(`/api/agent/sessions/${session.id}/events`);
    eventSourceRef.current = source;

    const eventNames = [
      "session.created",
      "agent.stage",
      "agent.message",
      "agent.decision_required",
      "agent.snapshot",
      "agent.completed",
      "agent.error"
    ];
    eventNames.forEach((name) => {
      source.addEventListener(name, (event) => {
        const parsed = JSON.parse((event as MessageEvent).data) as AgentEvent;
        setEvents((current) => mergeEvent(current, parsed));
      });
    });
    source.onerror = () => {
      source.close();
    };
    return () => source.close();
  }, [session?.id]);

  async function start() {
    if (!input.trim()) {
      return;
    }
    setLoading(true);
    setEvents([]);
    try {
      const created = await createSession(input.trim());
      setSession(created);
      setInput("");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "创建会话失败");
    } finally {
      setLoading(false);
    }
  }

  async function act(action: AgentAction, fallbackMessage: string) {
    if (!session) {
      return;
    }
    const text = action === "advise" || action === "revise" ? advice.trim() : "";
    if ((action === "advise" || action === "revise") && !text) {
      toast.warning("先输入你的建议。");
      return;
    }
    setLoading(true);
    try {
      const updated = await sendMessage({
        sessionId: session.id,
        decisionId: pendingDecision?.id,
        action,
        message: text || fallbackMessage
      });
      setSession(updated);
      setAdvice("");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "发送失败");
    } finally {
      setLoading(false);
    }
  }

  const eventTimeline = useMemo(
    () =>
      events
        .filter((event) => event.event !== "agent.snapshot")
        .slice(-8)
        .map((event) => ({
          color: event.event === "agent.error" ? "red" : event.event === "agent.completed" ? "green" : "blue",
          children: <Text className="event-line">{eventLabel(event)}</Text>
        })),
    [events]
  );

  return (
    <Layout className="app-shell">
      <Content className="main-panel">
        <Flex align="center" justify="space-between" className="topbar">
          <div>
            <Text className="eyebrow">AI Travel Agent</Text>
            <Title level={2}>对话式旅行规划</Title>
          </div>
          <Badge status={session?.stage === "completed" ? "success" : loading ? "processing" : "default"} text={stageLabels[session?.stage ?? ""] ?? "未开始"} />
        </Flex>

        <Card className="chat-card">
          <List
            className="message-list"
            dataSource={session?.messages ?? []}
            locale={{ emptyText: "输入旅行需求后，Agent 会分阶段规划并等待你的建议。" }}
            renderItem={(item: ChatMessage) => (
              <List.Item className={`message-row ${item.role}`}>
                <div className="message-bubble">
                  <Text strong>{item.role === "user" ? "你" : "Agent"}</Text>
                  <Paragraph>{item.content}</Paragraph>
                </div>
              </List.Item>
            )}
          />
          <Divider />
          {!session ? (
            <Space.Compact className="composer">
              <TextArea value={input} onChange={(event) => setInput(event.target.value)} autoSize={{ minRows: 2, maxRows: 5 }} />
              <Button type="primary" icon={<SendOutlined />} loading={loading} onClick={start}>
                开始
              </Button>
            </Space.Compact>
          ) : (
            <DecisionComposer
              decision={pendingDecision}
              advice={advice}
              loading={loading}
              onAdviceChange={setAdvice}
              onAction={act}
            />
          )}
        </Card>
      </Content>

      <Sider width={430} className="side-panel">
        <Space direction="vertical" size={16} className="side-stack">
          <DecisionPanel decision={pendingDecision} />
          <SnapshotPanel snapshot={latestSnapshot} />
          <Card title="Agent 过程">
            {eventTimeline.length ? <Timeline items={eventTimeline} /> : <Text type="secondary">暂无事件</Text>}
          </Card>
        </Space>
      </Sider>
    </Layout>
  );
}

function DecisionComposer(props: {
  decision: DecisionCard | null;
  advice: string;
  loading: boolean;
  onAdviceChange: (value: string) => void;
  onAction: (action: AgentAction, fallbackMessage: string) => void;
}) {
  if (!props.decision) {
    return (
      <Alert
        type="success"
        showIcon
        message="当前没有待处理决策"
        description="如果方案已经完成，可以基于右侧结果继续查看。"
      />
    );
  }
  return (
    <Space direction="vertical" className="composer">
      <TextArea
        value={props.advice}
        onChange={(event) => props.onAdviceChange(event.target.value)}
        placeholder="输入你的建议，例如：酒店想更靠近西湖，第二天节奏放松一点。"
        autoSize={{ minRows: 2, maxRows: 5 }}
      />
      <Flex wrap="wrap" gap={8}>
        <Button type="primary" icon={<CheckCircleOutlined />} loading={props.loading} onClick={() => props.onAction("confirm", "确认继续")}>
          确认继续
        </Button>
        <Button icon={<CheckCircleOutlined />} loading={props.loading} onClick={() => props.onAction("accept", "采纳推荐")}>
          采纳推荐
        </Button>
        <Button icon={<EditOutlined />} loading={props.loading} onClick={() => props.onAction("advise", "补充建议")}>
          补充建议
        </Button>
        <Button icon={<SyncOutlined />} loading={props.loading} onClick={() => props.onAction("revise", "要求调整")}>
          要求调整
        </Button>
      </Flex>
    </Space>
  );
}

function DecisionPanel({ decision }: { decision: DecisionCard | null }) {
  if (!decision) {
    return <Alert type="info" showIcon message="无待确认决策" description="Agent 会在关键节点暂停并等待你的建议。" />;
  }
  return (
    <Card title={decision.title}>
      <Space direction="vertical">
        <Tag color="processing">{stageLabels[decision.stage]}</Tag>
        <Paragraph>{decision.summary}</Paragraph>
        <Alert type="info" showIcon message={decision.recommended_action} />
        <Space wrap>
          {decision.options.map((option) => (
            <Tag key={option}>{option}</Tag>
          ))}
        </Space>
      </Space>
    </Card>
  );
}

function SnapshotPanel({ snapshot }: { snapshot: AgentSnapshot | null }) {
  if (!snapshot) {
    return (
      <Card title="方案快照">
        <Spin spinning={false}>
          <Text type="secondary">暂无方案。</Text>
        </Spin>
      </Card>
    );
  }
  const quotes = [...snapshot.transport_options, ...snapshot.hotel_options, ...snapshot.attraction_options];
  const total = quotes
    .filter((quote) => snapshot.selected_quote_ids.includes(quote.id))
    .reduce((sum, quote) => sum + quote.price_cny, 0);

  return (
    <Card title="方案快照">
      <Space direction="vertical" size={12} className="side-stack">
        <Paragraph>{snapshot.summary}</Paragraph>
        <Statistic title="已选报价估算" value={total || "-"} suffix={total ? "CNY" : ""} />
        <Divider orientation="left">行程</Divider>
        <List
          size="small"
          dataSource={snapshot.itinerary}
          locale={{ emptyText: "暂无行程草案" }}
          renderItem={(day) => (
            <List.Item>
              <Col>
                <Text strong>{String(day.title ?? `第 ${day.day} 天`)}</Text>
                <div className="meta-line">{[day.morning, day.afternoon, day.evening].filter(Boolean).join(" / ")}</div>
              </Col>
            </List.Item>
          )}
        />
        <Divider orientation="left">报价</Divider>
        <List
          size="small"
          dataSource={quotes}
          locale={{ emptyText: "预算阶段后展示报价" }}
          renderItem={(quote: QuoteOption) => (
            <List.Item>
              <Col>
                <Text strong>{quote.name}</Text>
                <div className="meta-line">
                  {quote.provider} · {quote.price_cny} CNY
                </div>
              </Col>
            </List.Item>
          )}
        />
        <Divider orientation="left">订单</Divider>
        <List
          size="small"
          dataSource={snapshot.bookings}
          locale={{ emptyText: "最终确认后生成 mock 订单" }}
          renderItem={(booking) => (
            <List.Item>
              <Col>
                <Text strong>{booking.id}</Text>
                <div className="meta-line">{booking.note}</div>
              </Col>
            </List.Item>
          )}
        />
      </Space>
    </Card>
  );
}

function mergeEvent(current: AgentEvent[], next: AgentEvent) {
  const key = `${next.event}-${next.created_at}`;
  if (current.some((item) => `${item.event}-${item.created_at}` === key)) {
    return current;
  }
  return [...current, next];
}

function eventLabel(event: AgentEvent) {
  if (event.event === "agent.stage") {
    return `进入阶段：${stageLabels[String(event.data.stage)] ?? event.data.stage}`;
  }
  if (event.event === "agent.message") {
    return String(event.data.content ?? "Agent 消息");
  }
  if (event.event === "agent.decision_required") {
    return `等待决策：${String(event.data.title ?? "")}`;
  }
  if (event.event === "agent.completed") {
    return "方案已完成";
  }
  if (event.event === "agent.error") {
    return String(event.data.message ?? "模型调用失败");
  }
  return event.event;
}

