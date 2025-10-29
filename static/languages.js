const translations = {
    zh: {
        // Header
        title: 'IPTV Stream Sniffer',
        subtitle: '测试IPTV流并捕获截图',

        // Tabs
        streamTest: '流测试',
        tvChannels: '电视频道',
        tvGroups: '电视分组',
        advancedSettings: '高级设置',

        // Test Tab
        testConfiguration: '测试配置',
        baseUrl: '基础URL',
        baseUrlHint: 'IPTV流的基础URL（使用{ip}作为IP地址占位符）',
        startIp: '起始IP',
        endIp: '结束IP',
        startTest: '开始测试',
        testProgress: '测试进度',
        testing: '测试中',
        testResults: '测试结果',
        all: '全部',
        success: '成功',
        failed: '失败',
        resolution: '分辨率',
        retry: '重试',

        // Channels Tab
        channelsLibrary: '电视频道库',
        importM3u: '导入M3U',
        syncMetadata: '同步元数据',
        aiRecognize: 'AI识别频道',
        clearNames: '清空频道名',
        exportM3u: '导出M3U',
        totalChannels: '共',
        channels: '个频道',
        ungrouped: '未分组',
        filterByGroup: '按分组筛选',
        filterByIp: '按IP筛选',
        filterByResolution: '按分辨率筛选',
        filterByConnectivity: '连通性筛选',
        searchIpHint: '输入IP进行搜索（如 192.168 或 248.10）',
        searchIpOrNameHint: '输入IP或频道名进行搜索（如 192.168 或 CCTV）',

        // Import M3U
        importM3uTitle: '导入M3U文件',
        selectM3uFile: '选择M3U文件',
        m3uFileHint: '支持 .m3u 和 .m3u8 格式',
        startImport: '开始导入',
        importing: '导入中...',
        importSuccess: '导入成功',

        // Sync Metadata
        confirmSyncMetadata: '确认从配置的URL同步元数据（logo、catchup等）？\n这将根据频道名匹配并更新现有频道的元数据。',
        syncing: '同步中...',

        // Table Headers
        screenshot: '截图',
        logo: '台标',
        ip: 'IP',
        channelName: '频道名',
        tvgId: 'TVG ID',
        resolution: '分辨率',
        connectivity: '连通性',
        group: '分组',
        url: 'URL',
        playback: '回放',
        updateTime: '更新时间',

        // Connectivity
        testConnectivity: '测试连通性',
        online: '在线',
        offline: '离线',
        testing: '测试中',
        untested: '未测试',

        // Groups Tab
        groupsManagement: '分组管理',
        newGroup: '新建分组',
        groups: '分组',
        dragToReorder: '拖动排序',
        selectGroup: '选择分组',
        addChannels: '添加频道',
        removeSelected: '移除选中',
        selectAll: '全选',
        noGroups: '暂无分组。点击"新建分组"创建一个。',
        noChannels: '此分组暂无频道',

        // Settings Tab
        advancedSettingsTitle: '高级设置',
        language: '语言',
        timeout: '超时（秒）',
        timeoutHint: '等待流响应的最大时间',
        queueSize: '并发队列大小',
        queueSizeHint: '同时测试的流数量（默认：5）',
//        customParams: '自定义FFmpeg参数',
//        customParamsHint: '附加的FFmpeg参数（如硬件加速）',

        // URL Configuration
        urlConfig: 'URL配置',
        externalBaseUrl: '外网Base URL',
        externalBaseUrlHint: '导出M3U时使用外网URL替换内网URL（可选）',

        // Metadata Source Configuration
        metadataSourceConfig: '元数据源配置',
        metadataSourceUrl: '元数据源URL',
        metadataSourceUrlHint: '在线元数据文件地址，支持M3U和Markdown格式，多个URL用逗号或换行分隔',
        epgUrl: 'EPG URL',
        epgUrlHint: 'EPG节目指南数据源地址（XML格式）',

        // Database Configuration
        databaseConfig: '数据库配置',
        databaseType: '数据库类型',
        databaseTypeHint: '选择数据存储方式',
        host: '主机',
        port: '端口',
        database: '数据库名',
        user: '用户名',
        password: '密码',

        // AI Settings
        aiConfiguration: 'AI模型配置',
        enableAi: '启用AI频道识别',
        enableAiHint: '启用AI模型自动从截图识别频道名称',
        aiApiUrl: 'AI API URL',
        apiKey: 'API密钥',
        apiKeyHint: '您的AI模型API密钥（将安全存储）',
        model: '模型',
        modelHint: 'AI模型名称（如 gpt-4-vision-preview、claude-3-opus）',

        // Scheduled Tasks
        scheduledTasksConfig: '定时任务配置',
        enableTestConnectivitySchedule: '启用定时连通性测试',
        enableTestConnectivityScheduleHint: '自动周期性测试所有频道的连通性',
        testConnectivityInterval: '连通性测试间隔（小时）',
        testConnectivityIntervalHint: '每隔多少小时执行一次连通性测试（默认24小时）',
        testConnectivityLastRun: '最后运行时间',
        enableSyncMetadataSchedule: '启用定时元数据同步',
        enableSyncMetadataScheduleHint: '自动周期性从在线源同步频道元数据',
        syncMetadataInterval: '元数据同步间隔（小时）',
        syncMetadataIntervalHint: '每隔多少小时执行一次元数据同步（默认168小时/7天）',
        syncMetadataLastRun: '最后运行时间',

        saveConfig: '保存配置',

        // Modals
        enterGroupName: '输入分组名称',
        addChannelsToGroup: '添加频道到分组',
        searchChannels: '搜索频道...',
        confirm: '确认',
        cancel: '取消',
        save: '保存',

        // Placeholders
        noImage: '无图像',
        streamOk: '流正常',
        noScreenshot: '无截图',
        unnamed: '未命名',
        noLogo: '无',

        // Messages
        testCompleted: '测试完成',
        configSaved: '配置已保存',
        groupCreated: '分组已创建',
        groupDeleted: '分组已删除',
        channelsAdded: '频道已添加',
        channelsRemoved: '频道已移除',
        exportSuccess: 'M3U文件已导出',

        // Actions
        edit: '编辑',
        delete: '删除',
        rename: '重命名',
        copy: '复制',
        clickToCopy: '点击复制',
        clickToEnlarge: '点击放大'
    },

    en: {
        // Header
        title: 'IPTV Stream Sniffer',
        subtitle: 'Test IPTV streams and capture screenshots',

        // Tabs
        streamTest: 'Stream Test',
        tvChannels: 'TV Channels',
        tvGroups: 'TV Groups',
        advancedSettings: 'Advanced Settings',

        // Test Tab
        testConfiguration: 'Test Configuration',
        baseUrl: 'Base URL',
        baseUrlHint: 'The base URL for IPTV streams (use {ip} as placeholder for IP address)',
        startIp: 'Start IP',
        endIp: 'End IP',
        startTest: 'Start Test',
        testProgress: 'Test Progress',
        testing: 'Testing',
        testResults: 'Test Results',
        all: 'All',
        success: 'Success',
        failed: 'Failed',
        resolution: 'Resolution',
        retry: 'Retry',

        // Channels Tab
        channelsLibrary: 'TV Channels Library',
        importM3u: 'Import M3U',
        syncMetadata: 'Sync Metadata',
        aiRecognize: 'AI Recognize',
        clearNames: 'Clear Names',
        exportM3u: 'Export M3U',
        totalChannels: 'Total',
        channels: 'channels',
        ungrouped: 'Ungrouped',
        filterByGroup: 'Filter by Group',
        filterByIp: 'Filter by IP',
        filterByResolution: 'Filter by Resolution',
        filterByConnectivity: 'Filter by Connectivity',
        searchIpHint: 'Enter IP to search (e.g. 192.168 or 248.10)',
        searchIpOrNameHint: 'Enter IP or channel name to search (e.g. 192.168 or CCTV)',

        // Import M3U
        importM3uTitle: 'Import M3U File',
        selectM3uFile: 'Select M3U File',
        m3uFileHint: 'Supports .m3u and .m3u8 formats',
        startImport: 'Start Import',
        importing: 'Importing...',
        importSuccess: 'Import Successful',

        // Sync Metadata
        confirmSyncMetadata: 'Confirm syncing metadata (logo, catchup, etc.) from configured URL?\nThis will match channels by name and update their metadata.',
        syncing: 'Syncing...',

        // Table Headers
        screenshot: 'Screenshot',
        logo: 'Logo',
        ip: 'IP',
        channelName: 'Channel Name',
        tvgId: 'TVG ID',
        resolution: 'Resolution',
        connectivity: 'Connectivity',
        group: 'Group',
        url: 'URL',
        playback: 'Playback',
        updateTime: 'Update Time',

        // Connectivity
        testConnectivity: 'Test Connectivity',
        online: 'Online',
        offline: 'Offline',
        testing: 'Testing',
        untested: 'Untested',

        // Groups Tab
        groupsManagement: 'Groups Management',
        newGroup: 'New Group',
        groups: 'Groups',
        dragToReorder: 'Drag to reorder',
        selectGroup: 'Select a group',
        addChannels: 'Add Channels',
        removeSelected: 'Remove Selected',
        selectAll: 'Select All',
        noGroups: 'No groups yet. Click "New Group" to create one.',
        noChannels: 'No channels in this group yet',

        // Settings Tab
        advancedSettingsTitle: 'Advanced Settings',
        language: 'Language',
        timeout: 'Timeout (seconds)',
        timeoutHint: 'Maximum time to wait for stream response',
        queueSize: 'Concurrent Queue Size',
        queueSizeHint: 'Number of streams to test simultaneously (default: 5)',
        customParams: 'Custom FFmpeg Parameters',
        customParamsHint: 'Additional FFmpeg parameters (e.g., hardware acceleration)',

        // URL Configuration
        urlConfig: 'URL Configuration',
        externalBaseUrl: 'External Base URL',
        externalBaseUrlHint: 'Replace internal URLs with external URLs when exporting M3U (optional)',

        // Metadata Source Configuration
        metadataSourceConfig: 'Metadata Source Configuration',
        metadataSourceUrl: 'Metadata Source URL',
        metadataSourceUrlHint: 'Online metadata file URLs (M3U, Markdown). Separate multiple URLs with comma or newline',
        epgUrl: 'EPG URL',
        epgUrlHint: 'EPG program guide data source URL (XML format)',

        // Database Configuration
        databaseConfig: 'Database Configuration',
        databaseType: 'Database Type',
        databaseTypeHint: 'Select data storage method',
        host: 'Host',
        port: 'Port',
        database: 'Database',
        user: 'User',
        password: 'Password',

        // AI Settings
        aiConfiguration: 'AI Model Configuration',
        enableAi: 'Enable AI Channel Recognition',
        enableAiHint: 'Enable AI model to automatically recognize channel names from screenshots',
        aiApiUrl: 'AI API URL',
        apiKey: 'API Key',
        apiKeyHint: 'Your AI model API key (will be stored securely)',
        model: 'Model',
        modelHint: 'AI model name (e.g., gpt-4-vision-preview, claude-3-opus)',

        // Scheduled Tasks
        scheduledTasksConfig: 'Scheduled Tasks Configuration',
        enableTestConnectivitySchedule: 'Enable Scheduled Connectivity Test',
        enableTestConnectivityScheduleHint: 'Automatically test connectivity of all channels periodically',
        testConnectivityInterval: 'Connectivity Test Interval (hours)',
        testConnectivityIntervalHint: 'How often to run connectivity test (default: 24 hours)',
        testConnectivityLastRun: 'Last Run Time',
        enableSyncMetadataSchedule: 'Enable Scheduled Metadata Sync',
        enableSyncMetadataScheduleHint: 'Automatically sync channel metadata from online sources periodically',
        syncMetadataInterval: 'Metadata Sync Interval (hours)',
        syncMetadataIntervalHint: 'How often to run metadata sync (default: 168 hours / 7 days)',
        syncMetadataLastRun: 'Last Run Time',

        saveConfig: 'Save Configuration',

        // Modals
        enterGroupName: 'Enter group name',
        addChannelsToGroup: 'Add Channels to Group',
        searchChannels: 'Search channels...',
        confirm: 'Confirm',
        cancel: 'Cancel',
        save: 'Save',

        // Placeholders
        noImage: 'No Image',
        streamOk: 'Stream OK',
        noScreenshot: 'No Screenshot',
        unnamed: 'Unnamed',
        noLogo: 'None',

        // Messages
        testCompleted: 'Test completed',
        configSaved: 'Configuration saved',
        groupCreated: 'Group created',
        groupDeleted: 'Group deleted',
        channelsAdded: 'Channels added',
        channelsRemoved: 'Channels removed',
        exportSuccess: 'M3U file exported',

        // Actions
        edit: 'Edit',
        delete: 'Delete',
        rename: 'Rename',
        copy: 'Copy',
        clickToCopy: 'Click to copy',
        clickToEnlarge: 'Click to enlarge'
    }
};

// Language manager
class LanguageManager {
    constructor() {
        this.currentLang = localStorage.getItem('language') || 'zh';
    }

    get(key) {
        const keys = key.split('.');
        let value = translations[this.currentLang];
        for (const k of keys) {
            value = value[k];
            if (!value) return key; // Return key if translation not found
        }
        return value;
    }

    setLanguage(lang) {
        this.currentLang = lang;
        localStorage.setItem('language', lang);
        this.updatePageLanguage();
    }

    getLanguage() {
        return this.currentLang;
    }

    updatePageLanguage() {
        // Update all elements with data-i18n attribute
        document.querySelectorAll('[data-i18n]').forEach(element => {
            const key = element.getAttribute('data-i18n');
            element.textContent = this.get(key);
        });

        // Update placeholders
        document.querySelectorAll('[data-i18n-placeholder]').forEach(element => {
            const key = element.getAttribute('data-i18n-placeholder');
            element.placeholder = this.get(key);
        });

        // Update titles
        document.querySelectorAll('[data-i18n-title]').forEach(element => {
            const key = element.getAttribute('data-i18n-title');
            element.title = this.get(key);
        });
    }
}

// Create global instance
const i18n = new LanguageManager();