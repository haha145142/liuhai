const { createApp, ref, computed, onMounted, onBeforeUnmount } = Vue;

const DEMO_INDEX_FALLBACK = [
  {code:'000001',name:'上证指数',price:3850.2,change_pct:0.82},
  {code:'000300',name:'沪深300',price:4522.1,change_pct:0.95},
  {code:'000905',name:'中证500',price:6844.5,change_pct:1.26},
  {code:'399006',name:'创业板指',price:2780.8,change_pct:1.81},
  {code:'HSI',name:'恒生指数',price:25840.3,change_pct:-0.32},
  {code:'IXIC',name:'纳斯达克',price:21540.2,change_pct:0.44},
];

async function api(path) {
  const res = await fetch(path, {headers:{'Accept':'application/json'}});
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

createApp({
  setup() {
    const funds = ref([]);
    const indices = ref([]);
    const industries = ref([]);
    const selected = ref(null);
    const holdings = ref([]);
    const loading = ref(true);
    const lastUpdated = ref(null);
    const error = ref('');
    let timer = null;

    const selectedEstimate = computed(() => {
      return funds.value.find(f => f.fund_code === selected.value) || null;
    });

    const totalChange = computed(() => {
      if (!funds.value.length) return 0;
      return funds.value.reduce((s,f)=>s+Number(f.change_pct ?? f.estimated_change_pct ?? 0),0)/funds.value.length;
    });

    const heatmap = computed(() => industries.value.map(x => ({...x, size: Math.max(1, Math.abs(Number(x.change_pct))) })));

    async function refresh() {
      error.value = '';
      try {
        const [fundRes, idxRes, indRes] = await Promise.all([
          api('/api/funds'), api('/api/market/indices'), api('/api/market/industries')
        ]);
        funds.value = fundRes.data || [];
        indices.value = idxRes.data || DEMO_INDEX_FALLBACK;
        industries.value = indRes.data || [];
        if (!selected.value && funds.value.length) selected.value = funds.value[0].fund_code;
        if (selected.value) {
          const [est, hs] = await Promise.all([
            api(`/api/funds/${selected.value}/estimate`),
            api(`/api/funds/${selected.value}/holdings`)
          ]);
          const item = funds.value.find(f=>f.fund_code===selected.value);
          if (item && est.data) Object.assign(item, est.data);
          holdings.value = hs.data || [];
        }
        lastUpdated.value = new Date();
      } catch (e) {
        error.value = '行情接口暂不可用，已保留当前数据。';
      } finally { loading.value = false; }
    }

    async function choose(code) {
      selected.value = code;
      try {
        const [est, hs] = await Promise.all([
          api(`/api/funds/${code}/estimate`), api(`/api/funds/${code}/holdings`)
        ]);
        const item = funds.value.find(f=>f.fund_code===code);
        if (item && est.data) Object.assign(item, est.data);
        holdings.value = hs.data || [];
      } catch (_) {}
    }

    function pct(v) {
      const n = Number(v || 0);
      return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`;
    }

    onMounted(() => {
      refresh();
      timer = setInterval(refresh, 30000);
    });
    onBeforeUnmount(() => clearInterval(timer));

    return { funds, indices, industries, selected, selectedEstimate, holdings, loading, lastUpdated, error, totalChange, heatmap, refresh, choose, pct };
  },
  template: `
  <div class="app-shell">
    <header class="topbar glass">
      <div><div class="eyebrow">FUND WATCH</div><h1>基金看盘</h1></div>
      <div class="status"><span class="dot"></span>盘中估值 · 30秒刷新</div>
    </header>

    <main class="page">
      <section class="hero glass">
        <div><div class="label">自选组合</div><div class="hero-num">{{ pct(totalChange) }}</div><div class="muted">组合平均盘中估算涨跌 · 非官方净值</div></div>
        <div class="hero-meta"><span>数据模式</span><strong>{{ funds.length && funds[0].source === 'postgres' ? 'PostgreSQL' : 'Demo' }}</strong><small>{{ lastUpdated ? '更新 '+lastUpdated.toLocaleTimeString() : '正在同步…' }}</small></div>
      </section>

      <section class="section-title"><div><span class="eyebrow">WATCHLIST</span><h2>我的自选</h2></div><button @click="refresh" class="icon-btn">↻</button></section>
      <section class="cards">
        <button v-for="fund in funds" :key="fund.fund_code" @click="choose(fund.fund_code)" :class="['fund-card glass', {active:selected===fund.fund_code}]">
          <div class="fund-head"><span>{{ fund.fund_name }}</span><span class="confidence">{{ fund.confidence || '—' }}</span></div>
          <div class="fund-code">{{ fund.fund_code }} · {{ fund.fund_type || '基金' }}</div>
          <div class="fund-change" :class="Number(fund.estimated_change_pct ?? fund.change_pct) >= 0 ? 'up':'down'">{{ pct(fund.estimated_change_pct ?? fund.change_pct) }}</div>
          <div class="fund-nav">估算净值 {{ Number(fund.estimated_nav ?? fund.nav).toFixed(4) }}</div>
        </button>
      </section>

      <section class="grid two">
        <div class="panel glass"><div class="panel-title"><span>市场指数</span><small>主要宽基</small></div><div class="index-grid"><div v-for="x in indices" class="index-item"><div>{{x.name}}</div><strong>{{x.price}}</strong><span :class="Number(x.change_pct)>=0?'up':'down'">{{pct(x.change_pct)}}</span></div></div></div>
        <div class="panel glass"><div class="panel-title"><span>行业雷达</span><small>当日涨跌</small></div><div class="industry-list"><div v-for="x in heatmap" class="industry"><span>{{x.name}}</span><div class="bar"><i :style="{width: Math.min(100, x.size*16)+'%'}"></i></div><b :class="Number(x.change_pct)>=0?'up':'down'">{{pct(x.change_pct)}}</b></div></div></div>
      </section>

      <section class="section-title"><div><span class="eyebrow">LOOK-THROUGH</span><h2>{{ selectedEstimate?.fund_name || '选择一只基金' }}</h2></div><span class="pill">持仓穿透</span></section>
      <section class="panel glass holdings"><div class="holding-row holding-header"><span>股票</span><span>权重</span><span>盘中涨跌</span></div><div v-for="h in holdings" class="holding-row"><span><b>{{h.stock_name}}</b><small>{{h.stock_code}}</small></span><span>{{Number(h.weight).toFixed(2)}}%</span><span :class="Number(h.current_change_pct)>=0?'up':'down'">{{pct(h.current_change_pct)}}</span></div><div v-if="!holdings.length" class="empty">选择基金查看前十大持仓穿透。</div></section>

      <div v-if="error" class="notice">{{error}}</div>
      <div class="footer-note">估算值仅用于盘中辅助判断，不代表基金实际成交或官方净值。</div>
    </main>
  </div>`
}).mount('#app');
