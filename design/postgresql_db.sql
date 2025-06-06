-- 序列替代自增主键
CREATE SEQUENCE hktlora_leads_lead_id_seq;
CREATE SEQUENCE companies_company_id_seq;
CREATE SEQUENCE interactions_interaction_id_seq;
CREATE SEQUENCE campaigns_campaign_id_seq;
CREATE SEQUENCE opportunities_opportunity_id_seq;
CREATE SEQUENCE users_user_id_seq;
CREATE SEQUENCE notes_note_id_seq;

-- 线索表：存储线索的基本信息，客户在hktlora网站上提交的表单信息
CREATE TABLE hktlora_leads (
    lead_id BIGINT PRIMARY KEY DEFAULT nextval('hktlora_leads_lead_id_seq'),
    submission_date VARCHAR(30), -- 提交日期，格式为YYYY-MM-DD HH:MM:SS
    first_name VARCHAR(50), -- First Name
    last_name VARCHAR(50), -- Last Name
    email VARCHAR(100) , -- Email Address
    phone VARCHAR(20), -- WhatsApp/Phone NO.
    country VARCHAR(50), -- 国家
    postcode VARCHAR(20), -- 邮编
    message TEXT, -- 留言
    source_link VARCHAR(100), -- 线索来源链接
    lead_score INT DEFAULT 0, -- 线索评分（0-100）
    lead_status VARCHAR(20) CHECK (lead_status IN ('新', '暖', '热' , '成交', '无效')) DEFAULT '新', -- 线索状态
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 创建触发器函数来自动更新updated_at字段
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 为leads表创建触发器
CREATE TRIGGER update_leads_updated_at
BEFORE UPDATE ON leads
FOR EACH ROW
EXECUTE FUNCTION update_updated_at();

-- 公司表：存储线索关联的公司信息，避免重复存储
CREATE TABLE companies (
    company_id BIGINT PRIMARY KEY DEFAULT nextval('companies_company_id_seq'),
    company_name VARCHAR(100) NOT NULL,
    industry VARCHAR(50),
    website VARCHAR(100),
    address TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 线索与公司关联表（多对多关系）
CREATE TABLE lead_company (
    lead_id BIGINT,
    company_id BIGINT,
    PRIMARY KEY (lead_id, company_id),
    FOREIGN KEY (lead_id) REFERENCES leads(lead_id) ON DELETE CASCADE,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE
);

-- 交互记录表：存储与线索的每次交互（如邮件、电话、会议）
CREATE TABLE interactions (
    interaction_id BIGINT PRIMARY KEY DEFAULT nextval('interactions_interaction_id_seq'),
    lead_id BIGINT,
    interaction_type VARCHAR(20) CHECK (interaction_type IN ('email', 'call', 'meeting', 'webinar', 'social_media')) NOT NULL,
    interaction_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    description TEXT,
    outcome VARCHAR(100), -- 交互结果（如"已回复"、"无回应"）
    FOREIGN KEY (lead_id) REFERENCES leads(lead_id) ON DELETE CASCADE
);

-- 营销活动表：存储营销活动信息（如邮件营销、广告投放）
CREATE TABLE campaigns (
    campaign_id BIGINT PRIMARY KEY DEFAULT nextval('campaigns_campaign_id_seq'),
    campaign_name VARCHAR(100) NOT NULL,
    campaign_type VARCHAR(20) CHECK (campaign_type IN ('email', 'social_media', 'webinar', 'ads')) NOT NULL,
    start_date DATE,
    end_date DATE,
    budget DECIMAL(10, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 线索与营销活动关联表：记录线索参与的营销活动
CREATE TABLE lead_campaign (
    lead_id BIGINT,
    campaign_id BIGINT,
    engagement_score INT DEFAULT 0, -- 参与度评分
    engaged_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (lead_id, campaign_id),
    FOREIGN KEY (lead_id) REFERENCES leads(lead_id) ON DELETE CASCADE,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id) ON DELETE CASCADE
);

-- 销售机会表：存储从线索转化的销售机会
CREATE TABLE opportunities (
    opportunity_id BIGINT PRIMARY KEY DEFAULT nextval('opportunities_opportunity_id_seq'),
    lead_id BIGINT,
    opportunity_name VARCHAR(100) NOT NULL,
    amount DECIMAL(10, 2), -- 预计成交金额
    stage VARCHAR(20) CHECK (stage IN ('prospect', 'negotiation', 'proposal', 'closed_won', 'closed_lost')) NOT NULL,
    expected_close_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (lead_id) REFERENCES leads(lead_id) ON DELETE CASCADE
);

-- 为opportunities表创建触发器
CREATE TRIGGER update_opportunities_updated_at
BEFORE UPDATE ON opportunities
FOR EACH ROW
EXECUTE FUNCTION update_updated_at();

-- 用户表：存储销售和营销团队用户信息
CREATE TABLE users (
    user_id BIGINT PRIMARY KEY DEFAULT nextval('users_user_id_seq'),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    role VARCHAR(20) CHECK (role IN ('sales', 'marketing', 'admin')) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 线索分配表：记录线索分配给哪个销售人员
CREATE TABLE lead_assignment (
    lead_id BIGINT,
    user_id BIGINT,
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (lead_id, user_id),
    FOREIGN KEY (lead_id) REFERENCES leads(lead_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- 注释表：存储对线索的备注
CREATE TABLE notes (
    note_id BIGINT PRIMARY KEY DEFAULT nextval('notes_note_id_seq'),
    lead_id BIGINT,
    user_id BIGINT,
    note_content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (lead_id) REFERENCES leads(lead_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
