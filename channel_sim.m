%% 高阶高速移动信道仿真：动画增强版 (BJTU 孙涛 23211436)
clear; clc; close all;

%% 1. 场景参数
fc = 2.1e9;             
v_kmh = 350;            
v = v_kmh / 3.6;
D = 50;                 
L = 1000;               
fs = 200;               % 适当降低采样率，让动画更平滑

t_total = L/v;          % 自动计算通过路段所需时间
t = 0:1/fs:t_total;    
dist_x = -L/2 + v*t;    

% 核心物理量
R = sqrt(D^2 + dist_x.^2);
cos_theta = -dist_x ./ R;
fd_max = (v/3e8)*fc;
fd_dynamic = fd_max * cos_theta;
K_dB = 13 - 0.03 * R;

%% 2. 界面初始化
fig = figure('Color', 'w', 'Position', [50, 50, 1200, 700]);
sgtitle(['轨道交通移动信道动态仿真 - 演示模式 [孙涛 23211436]'], 'FontSize', 16);

% 子图布局
ax1 = subplot(2,2,1); hold on; grid on; axis equal;
xlim([-L/2-50, L/2+50]); ylim([-20, D+60]);
title('场景几何示意图 (实时更新)');

% 静态元素
plot([-L/2, L/2], [0, 0], 'k', 'LineWidth', 3); 
plot(0, D, 'r^', 'MarkerSize', 12, 'MarkerFaceColor', 'r'); 

% 动态句柄
h_train = plot(NaN, NaN, 'ks', 'MarkerSize', 15, 'MarkerFaceColor', [0 0.26 0.58]); 
h_los = plot(NaN, NaN, 'r--', 'LineWidth', 1);
h_txt = text(-L/2, D+40, '', 'FontSize', 10, 'FontWeight', 'bold');

% 数据图表初始化
ax2 = subplot(2,2,2); grid on; hold on; xlim([0, t_total]); ylim([-fd_max*1.1, fd_max*1.1]);
title('多普勒频移 (Hz)'); h_fd = animatedline('Color', 'b', 'LineWidth', 2);

ax3 = subplot(2,2,3); grid on; hold on; xlim([0, t_total]); ylim([min(K_dB)-2, max(K_dB)+2]);
title('莱斯 K 因子 (dB)'); h_k = animatedline('Color', [0.8 0.4 0], 'LineWidth', 2);

ax4 = subplot(2,2,4); grid on; hold on; xlim([0, t_total]); ylim([-1.1, 1.1]);
title('cos(\theta) 入射角余弦'); h_cos = animatedline('Color', 'g', 'LineWidth', 2);

%% 3. 动画循环 (核心修正)
fprintf('正在生成动画，请观察弹出的绘图窗口...\n');

% 步长控制：每隔 5 个点画一帧，增加观看流畅度
step = 5; 
for i = 1:step:length(t)
    % 更新几何图
    set(h_train, 'XData', dist_x(i), 'YData', 0);
    set(h_los, 'XData', [dist_x(i), 0], 'YData', [0, D]);
    set(h_txt, 'String', sprintf('当前位置: %.1fm | 瞬时频移: %.1f Hz', dist_x(i), fd_dynamic(i)));
    
    % 更新曲线
    addpoints(h_fd, t(i), fd_dynamic(i));
    addpoints(h_k, t(i), K_dB(i));
    addpoints(h_cos, t(i), cos_theta(i));
    
    % --- 关键：强制刷新并控制速度 ---
    drawnow; 
    pause(0.01); % 强制暂停 10 毫秒，否则 CPU 运行太快看不出动画
    
    % 检查窗口是否被关闭
    if ~ishandle(fig), break; end
end

fprintf('仿真演示结束。\n');