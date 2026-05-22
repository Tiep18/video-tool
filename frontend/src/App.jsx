import React, { useState, useEffect, useRef } from 'react';
import { 
  Layout, 
  Tabs, 
  Card, 
  Input, 
  Button, 
  Radio, 
  Slider, 
  Switch, 
  Upload, 
  Progress, 
  Tag, 
  Space, 
  Typography, 
  message, 
  Tooltip,
  Alert,
  Table,
  Row,
  Col,
  Badge,
  theme as antdTheme,
  ConfigProvider
} from 'antd';
import { 
  Video, 
  Key, 
  Music, 
  Languages, 
  FileText, 
  Trash2, 
  RefreshCw, 
  Play, 
  Download, 
  Sliders, 
  Settings, 
  Terminal, 
  AlertTriangle,
  UploadCloud,
  FileJson,
  Table as TableIcon
} from 'lucide-react';

const { Header, Content, Sider } = Layout;
const { Text } = Typography;

function VideoGeneratorApp() {
  // ── States ────────────────────────────────────────────────────────────────
  const [apiKey, setApiKey] = useState('');
  const [audioPath, setAudioPath] = useState('');
  const [originalAudioPath, setOriginalAudioPath] = useState('');
  const [audioSpeed, setAudioSpeed] = useState(1.0);
  const [audioTimestamp, setAudioTimestamp] = useState(Date.now());
  const [isChangingSpeed, setIsChangingSpeed] = useState(false);
  const [audioFilename, setAudioFilename] = useState('');
  const [audioSize, setAudioSize] = useState('');
  
  const [scenesText, setScenesText] = useState('');
  const [language, setLanguage] = useState('Tiếng Việt');
  const [matchedScenes, setMatchedScenes] = useState([]);
  const [previewMode, setPreviewMode] = useState(false);
  const [imagePaths, setImagePaths] = useState([]);
  
  // Render Settings
  const [resolution, setResolution] = useState('Dọc 9:16 (TikTok/Reels)');
  const [intensity, setIntensity] = useState(0.08);
  const [transitionDur, setTransitionDur] = useState(0.8);
  
  // Loading & Progress States
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isRendering, setIsRendering] = useState(false);
  const [renderProgress, setRenderProgress] = useState(0);
  const [renderStep, setRenderStep] = useState('Đang chờ lệnh...');
  const [consoleLogs, setConsoleLogs] = useState(['Console initialized...']);
  
  // Video Output
  const [videoUrl, setVideoUrl] = useState('');

  const consoleEndRef = useRef(null);
  const pendingFilesRef = useRef([]);
  const uploadTimeoutRef = useRef(null);

  // Auto scroll console logs
  useEffect(() => {
    if (consoleEndRef.current) {
      consoleEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [consoleLogs]);

  // Load cache on startup
  useEffect(() => {
    const savedApiKey = localStorage.getItem('openai_api_key');
    if (savedApiKey) {
      setApiKey(savedApiKey);
    }
    loadCache();
  }, []);

  // ── API Operations ────────────────────────────────────────────────────────
  const loadCache = async () => {
    try {
      const res = await fetch('/api/load-cache');
      if (!res.ok) return;
      const data = await res.json();
      
      if (data.api_key) {
        setApiKey(data.api_key);
        localStorage.setItem('openai_api_key', data.api_key);
      }
      if (data.audio_path) {
        setAudioPath(data.audio_path);
        setOriginalAudioPath(data.original_audio_path || data.audio_path);
        setAudioSpeed(data.audio_speed || 1.0);
        setAudioFilename(data.audio_filename || 'Audio đã lưu');
        setAudioSize('Cached File');
      }
      if (data.scenes_text) setScenesText(data.scenes_text);
      if (data.language) setLanguage(data.language);
      if (data.preview_mode) setPreviewMode(data.preview_mode);
      if (data.image_paths) setImagePaths(data.image_paths);
      if (data.matched_scenes) setMatchedScenes(data.matched_scenes);
    } catch (error) {
      console.error('Lỗi tải cache:', error);
      message.error('Không thể tải dữ liệu cache từ máy chủ.');
    }
  };

  const handleApiKeyChange = (e) => {
    const val = e.target.value.trim();
    setApiKey(val);
    localStorage.setItem('openai_api_key', val);
  };

  const handleUploadAudio = async ({ file }) => {
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const res = await fetch('/api/upload-audio', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (data.status === 'success') {
        setAudioPath(data.path);
        setOriginalAudioPath(data.original_path || data.path);
        setAudioSpeed(1.0);
        setAudioFilename(file.name);
        setAudioSize((file.size / 1024 / 1024).toFixed(2) + ' MB');
        setAudioTimestamp(Date.now());
        message.success('Tải lên audio thành công!');
      } else {
        throw new Error(data.message || 'Lỗi tải lên audio.');
      }
    } catch (error) {
      console.error(error);
      message.error('Lỗi tải lên file audio: ' + error.message);
    }
  };

  const handleRemoveAudio = () => {
    setAudioPath('');
    setOriginalAudioPath('');
    setAudioSpeed(1.0);
    setAudioFilename('');
    setAudioSize('');
  };

  const handleAudioSpeedChange = async (value) => {
    if (!audioPath || !originalAudioPath) return;
    
    setIsChangingSpeed(true);
    try {
      const res = await fetch('/api/change-audio-speed', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          original_audio_path: originalAudioPath,
          audio_path: audioPath,
          speed: value,
          api_key: apiKey,
          scenes_text: scenesText,
          language: language,
          matched_scenes: matchedScenes,
          preview_mode: previewMode
        })
      });
      
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Lỗi xử lý tốc độ audio.');
      }
      
      const data = await res.json();
      if (data.status === 'success') {
        setAudioPath(data.path || data.audio_path);
        setAudioSpeed(data.audio_speed);
        setMatchedScenes(data.matched_scenes);
        setAudioTimestamp(Date.now());
        message.success(`Đã thay đổi tốc độ audio sang ${value}x và tự động co giãn timeline!`);
      } else {
        throw new Error(data.message || 'Lỗi xử lý tốc độ audio.');
      }
    } catch (error) {
      console.error(error);
      message.error('Không thể thay đổi tốc độ: ' + error.message);
    } finally {
      setIsChangingSpeed(false);
    }
  };

  const performBatchImageUpload = async (files) => {
    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
      formData.append('files', files[i]);
    }

    try {
      const res = await fetch('/api/upload-images', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (data.status === 'success') {
        setImagePaths(data.paths);
        message.success(`Đã tải lên ${data.paths.length} ảnh phân cảnh!`);
      } else {
        throw new Error(data.message || 'Lỗi tải lên danh sách ảnh.');
      }
    } catch (error) {
      console.error(error);
      message.error('Lỗi tải lên ảnh: ' + error.message);
    }
  };

  const handleAnalyze = async () => {
    if (!apiKey.trim()) {
      message.warning('Vui lòng nhập OpenAI API Key.');
      return;
    }
    if (!audioPath) {
      message.warning('Vui lòng tải lên file Audio Voiceover trước.');
      return;
    }
    if (!scenesText.trim()) {
      message.warning('Vui lòng nhập nội dung phân cảnh.');
      return;
    }

    setIsAnalyzing(true);
    try {
      const res = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          api_key: apiKey,
          audio_path: audioPath,
          scenes_text: scenesText,
          language: language
        })
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Lỗi phân tích không rõ.');
      }

      const data = await res.json();
      setMatchedScenes(data.matched_scenes);
      message.success('Phân tích hoàn tất! Kiểm tra kết quả trong Timeline phía dưới.');
    } catch (error) {
      console.error(error);
      message.error('Lỗi phân tích: ' + error.message);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleSync = async () => {
    setIsSyncing(true);
    try {
      const res = await fetch('/api/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          api_key: apiKey,
          audio_path: audioPath,
          original_audio_path: originalAudioPath,
          audio_speed: audioSpeed,
          scenes_text: scenesText,
          language: language,
          matched_scenes: matchedScenes,
          preview_mode: previewMode
        })
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Lỗi đồng bộ.');
      }

      const data = await res.json();
      setMatchedScenes(data.matched_scenes);
      message.success('Đồng bộ timestamps thành công!');
    } catch (error) {
      console.error(error);
      message.error('Lỗi đồng bộ: ' + error.message);
    } finally {
      setIsSyncing(false);
    }
  };

  const handleClearCache = async () => {
    try {
      const res = await fetch('/api/clear-cache', { method: 'POST' });
      if (res.ok) {
        setApiKey('');
        localStorage.removeItem('openai_api_key');
        setAudioPath('');
        setAudioFilename('');
        setAudioSize('');
        setScenesText('');
        setLanguage('Tiếng Việt');
        setMatchedScenes([]);
        setPreviewMode(false);
        setImagePaths([]);
        setVideoUrl('');
        setRenderProgress(0);
        setRenderStep('Đang chờ lệnh...');
        setConsoleLogs(['Console initialized...']);
        message.success('Đã xóa sạch cache và tệp tạm thành công.');
      }
    } catch (error) {
      message.error('Lỗi xóa cache: ' + error.message);
    }
  };

  const handleExport = (format) => {
    window.open(`/api/export?format=${format}`, '_blank');
  };

  const handleRender = async () => {
    if (!audioPath) {
      message.warning('Vui lòng tải lên Audio trước.');
      return;
    }
    if (imagePaths.length === 0) {
      message.warning('Vui lòng tải lên ít nhất một ảnh phân cảnh.');
      return;
    }
    if (matchedScenes.length === 0) {
      message.warning('Chưa có dữ liệu phân cảnh. Vui lòng phân tích trước.');
      return;
    }

    // Reset progress UI
    setRenderProgress(0);
    setRenderStep('Khởi động tiến trình render...');
    setConsoleLogs(['→ Bắt đầu kết nối với render engine...']);
    setVideoUrl('');
    setIsRendering(true);

    try {
      const payload = {
        audio_path: audioPath,
        image_paths: imagePaths,
        resolution: resolution,
        intensity: intensity,
        transition_dur: transitionDur,
        preview_mode: previewMode
      };

      const response = await fetch('/api/render', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        throw new Error('Lỗi kết nối render server.');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value);
        const lines = buffer.split('\n\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (line.trim().startsWith('data: ')) {
            try {
              const data = JSON.parse(line.trim().substring(6));
              
              if (data.step) {
                setRenderStep(data.step);
                setConsoleLogs(prev => [...prev, `[${data.pct}%] ${data.step}`]);
              }
              if (data.pct !== undefined) {
                setRenderProgress(data.pct);
              }
              if (data.video_url) {
                setVideoUrl(data.video_url);
                message.success('Dựng video thành công!');
              }
            } catch (e) {
              console.error('Lỗi parse SSE JSON:', e);
            }
          }
        }
      }
    } catch (error) {
      console.error(error);
      setConsoleLogs(prev => [...prev, `❌ Lỗi hệ thống: ${error.message}`]);
      message.error('Render video thất bại: ' + error.message);
    } finally {
      setIsRendering(false);
    }
  };

  // ── Render Timeline Validation Helpers ────────────────────────────────────
  const validateTimeline = () => {
    const warnings = [];
    for (let i = 0; i < matchedScenes.length; i++) {
      const s = matchedScenes[i];
      if (s.end < s.start) {
        warnings.push(`Cảnh #${s.screen}: Out (${s.end}s) nhỏ hơn In (${s.start}s).`);
      }
      if (i > 0) {
        const prev = matchedScenes[i - 1];
        if (s.start < prev.end) {
          warnings.push(`Cảnh #${s.screen} bị đè thời gian với Cảnh #${prev.screen} (${s.start}s < ${prev.end}s).`);
        }
      }
    }
    return warnings;
  };

  const timelineWarnings = validateTimeline();

  const updateSceneValue = (index, field, value) => {
    const updated = [...matchedScenes];
    updated[index][field] = value;
    
    // Auto calculate duration
    if (field === 'start' || field === 'end') {
      const start = parseFloat(updated[index].start) || 0;
      const end = parseFloat(updated[index].end) || 0;
      updated[index].duration = Math.max(0, end - start);
    }
    
    setMatchedScenes(updated);
  };

  const getResolutionClass = () => {
    if (resolution.includes('16:9')) return 'landscape';
    if (resolution.includes('1:1')) return 'square';
    return 'portrait'; // 9:16
  };

  // ── Table Column Definition ───────────────────────────────────────────────
  const columns = [
    {
      title: '#',
      dataIndex: 'screen',
      key: 'screen',
      width: 50,
      align: 'center',
      render: (num) => <Text style={{ fontWeight: '600', color: '#8c92a6' }}>{num}</Text>,
    },
    {
      title: 'Độ khớp',
      dataIndex: 'match_pct',
      key: 'match_pct',
      width: 90,
      align: 'center',
      render: (pct) => {
        let color = 'error';
        let label = 'Kém';
        if (pct >= 60) {
          color = 'success';
          label = 'Tốt';
        } else if (pct >= 30) {
          color = 'warning';
          label = 'Khá';
        }
        return (
          <Tooltip title={`Tỉ lệ trùng khớp từ: ${pct}% (${label})`}>
            <Tag color={color} style={{ fontSize: '10px', margin: 0 }}>{pct}%</Tag>
          </Tooltip>
        );
      }
    },
    {
      title: 'Nội dung phân cảnh lời thoại',
      dataIndex: 'scene',
      key: 'scene',
      render: (text, record, index) => (
        <Input 
          value={text} 
          onChange={(e) => updateSceneValue(index, 'scene', e.target.value)}
          style={{ 
            background: '#0d0e12', 
            borderColor: '#22252c', 
            color: '#fff', 
            fontSize: '13px', 
            height: '32px'
          }} 
        />
      )
    },
    {
      title: 'In (s)',
      dataIndex: 'start',
      key: 'start',
      width: 100,
      render: (val, record, index) => {
        const hasOverlap = index > 0 && val < matchedScenes[index - 1].end;
        return (
          <Space size={4}>
            <input 
              type="number" 
              value={val} 
              step="0.05" 
              min="0"
              onChange={(e) => updateSceneValue(index, 'start', parseFloat(e.target.value) || 0)}
              style={{ 
                width: '75px', 
                background: '#0d0e12', 
                border: `1px solid ${hasOverlap ? '#ff4d4f' : '#22252c'}`, 
                borderRadius: '4px', 
                color: '#fff', 
                padding: '4px 6px', 
                fontSize: '12px',
                height: '32px',
                boxSizing: 'border-box',
                textAlign: 'center'
              }} 
            />
            {hasOverlap && (
              <Tooltip title={`Đè chéo thời gian với cảnh #${matchedScenes[index - 1].screen}`}>
                <AlertTriangle size={14} color="#ff4d4f" />
              </Tooltip>
            )}
          </Space>
        );
      }
    },
    {
      title: 'Out (s)',
      dataIndex: 'end',
      key: 'end',
      width: 100,
      render: (val, record, index) => {
        const hasTimeError = val < record.start;
        return (
          <Space size={4}>
            <input 
              type="number" 
              value={val} 
              step="0.05" 
              min="0"
              onChange={(e) => updateSceneValue(index, 'end', parseFloat(e.target.value) || 0)}
              style={{ 
                width: '75px', 
                background: '#0d0e12', 
                border: `1px solid ${hasTimeError ? '#ff4d4f' : '#22252c'}`, 
                borderRadius: '4px', 
                color: '#fff', 
                padding: '4px 6px', 
                fontSize: '12px',
                height: '32px',
                boxSizing: 'border-box',
                textAlign: 'center'
              }} 
            />
            {hasTimeError && (
              <Tooltip title="Thời gian kết thúc nhỏ hơn thời gian bắt đầu.">
                <AlertTriangle size={14} color="#ff4d4f" />
              </Tooltip>
            )}
          </Space>
        );
      }
    },
    {
      title: 'Thời lượng',
      dataIndex: 'duration',
      key: 'duration',
      width: 80,
      align: 'center',
      render: (dur) => (
        <Text style={{ 
          background: '#1a1d26', 
          color: '#8c92a6', 
          padding: '4px 8px', 
          borderRadius: '4px', 
          fontSize: '11px',
          fontWeight: '600'
        }}>
          {dur.toFixed(2)}s
        </Text>
      )
    }
  ];

  const dataSource = matchedScenes.map((item, index) => ({
    ...item,
    key: index
  }));

  // ── Render Workspace Layout ──────────────────────────────────────────────
  return (
    <Layout style={{ height: '100vh', overflow: 'hidden' }}>
      {/* Left Panel: All Configuration (AI Inputs & Render Settings in Tabs) */}
      <Sider width={320} className="sider-panel" trigger={null} style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
        <div style={{ 
          padding: '12px 16px', 
          borderBottom: '1px solid #22252c', 
          display: 'flex', 
          alignItems: 'center', 
          gap: '10px',
          height: '56px',
          boxSizing: 'border-box',
          flexShrink: 0
        }}>
          <Video size={20} color="#1677ff" />
          <div>
            <div style={{ color: '#fff', fontWeight: '700', fontSize: '14px', lineHeight: 1.1 }}>Auto Video Generator</div>
            <Text type="secondary" style={{ fontSize: '9px', display: 'block', color: 'rgba(255,255,255,0.35)' }}>AI Video Layout Workspace</Text>
          </div>
        </div>
        <div className="sider-content" style={{ display: 'flex', flexDirection: 'column', padding: '0 8px 12px 8px', overflowY: 'auto', flex: 1 }}>
          <Tabs
            defaultActiveKey="1"
            size="small"
            centered
            items={[
              {
                key: '1',
                label: '🎙️ Đầu vào AI',
                children: (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', padding: '12px 8px 0 8px' }}>
                    {/* OpenAI API Key */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.45)', fontWeight: '600', textTransform: 'uppercase' }}>🔑 OpenAI API Key</span>
                      <Input.Password 
                        placeholder="sk-proj-..." 
                        value={apiKey} 
                        onChange={handleApiKeyChange}
                        style={{ width: '100%', height: '32px' }}
                      />
                    </div>

                    {/* Audio Upload */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.45)', fontWeight: '600', textTransform: 'uppercase' }}>🎵 Audio Voiceover</span>
                      {!audioPath ? (
                        <Upload.Dragger
                          accept="audio/*"
                          showUploadList={false}
                          customRequest={handleUploadAudio}
                          className="compact-dragger"
                        >
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', padding: '6px 0' }}>
                            <UploadCloud size={16} color="#1677ff" />
                            <span style={{ fontSize: '12px', color: 'rgba(255,255,255,0.85)' }}>Kéo thả / Chọn Audio</span>
                          </div>
                        </Upload.Dragger>
                      ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                          <div style={{ 
                            display: 'flex', 
                            alignItems: 'center', 
                            justifyContent: 'space-between',
                            padding: '6px 10px', 
                            background: '#0d0e12', 
                            border: '1px solid #22252c', 
                            borderRadius: '4px',
                            height: '32px',
                            boxSizing: 'border-box'
                          }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', overflow: 'hidden' }}>
                              <Music size={14} color="#1677ff" style={{ flexShrink: 0 }} />
                              <span style={{ 
                                fontSize: '12px', 
                                color: '#fff', 
                                textOverflow: 'ellipsis', 
                                overflow: 'hidden', 
                                whiteSpace: 'nowrap',
                                maxWidth: '170px'
                              }}>
                                {audioFilename}
                              </span>
                            </div>
                            <Button 
                              type="text" 
                              danger 
                              size="small"
                              icon={<Trash2 size={12} />} 
                              onClick={handleRemoveAudio}
                              style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                            />
                          </div>

                          <audio 
                            src={audioPath ? `/uploads/audio/${encodeURIComponent(audioPath.split(/[/\\]/).pop())}?t=${audioTimestamp}` : ''} 
                            controls 
                            style={{ width: '100%', height: '32px' }} 
                          />

                          <div style={{ padding: '6px 8px', background: '#0d0e12', borderRadius: '4px', border: '1px solid #22252c' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2px' }}>
                              <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.45)', fontWeight: '600' }}>TỐC ĐỘ AUDIO</span>
                              <span style={{ fontSize: '11px', color: '#1677ff', fontWeight: 'bold' }}>{audioSpeed.toFixed(1)}x</span>
                            </div>
                            <Slider
                              min={0.5}
                              max={2.0}
                              step={0.1}
                              value={audioSpeed}
                              disabled={isChangingSpeed}
                              onChange={(val) => setAudioSpeed(val)}
                              onAfterChange={handleAudioSpeedChange}
                              tooltip={{ formatter: (value) => `${value}x` }}
                              style={{ margin: '6px 4px 8px 4px' }}
                            />
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Language Selection */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.45)', fontWeight: '600', textTransform: 'uppercase' }}>🌐 Ngôn Ngữ Whisper</span>
                      <Radio.Group 
                        value={language} 
                        onChange={(e) => setLanguage(e.target.value)} 
                        optionType="button" 
                        buttonStyle="solid"
                        style={{ width: '100%', display: 'flex' }}
                      >
                        <Radio.Button value="Tiếng Việt" style={{ flex: 1, fontSize: '11px', textAlign: 'center', height: '32px', lineHeight: '30px', padding: 0 }}>Tiếng Việt</Radio.Button>
                        <Radio.Button value="English" style={{ flex: 1, fontSize: '11px', textAlign: 'center', height: '32px', lineHeight: '30px', padding: 0 }}>English</Radio.Button>
                        <Radio.Button value="Tự động" style={{ flex: 1, fontSize: '11px', textAlign: 'center', height: '32px', lineHeight: '30px', padding: 0 }}>Tự động</Radio.Button>
                      </Radio.Group>
                    </div>

                    {/* Scenes input */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.45)', fontWeight: '600', textTransform: 'uppercase' }}>📋 Danh Sách Phân Cảnh</span>
                      <Input.TextArea
                        placeholder="Nhập nội dung phân cảnh lời thoại... Mỗi dòng một cảnh."
                        value={scenesText}
                        onChange={(e) => setScenesText(e.target.value)}
                        rows={10}
                        style={{ width: '100%', fontFamily: 'inherit', fontSize: '12px', background: '#0d0e12', borderColor: '#22252c' }}
                      />
                    </div>

                    {/* Actions */}
                    <div style={{ display: 'flex', gap: '8px', marginTop: '4px' }}>
                      <Button 
                        type="primary" 
                        icon={<RefreshCw size={12} style={{ marginRight: '4px' }} />}
                        loading={isAnalyzing}
                        onClick={handleAnalyze}
                        style={{ flex: 2, background: '#1677ff', borderColor: '#1677ff', height: '32px', fontSize: '12px' }}
                      >
                        Phân tích Timestamps
                      </Button>
                      <Button 
                        danger
                        icon={<Trash2 size={12} style={{ marginRight: '4px' }} />}
                        onClick={handleClearCache}
                        style={{ flex: 1, height: '32px', fontSize: '12px' }}
                      >
                        Clear
                      </Button>
                    </div>
                  </div>
                )
              },
              {
                key: '2',
                label: '⚙️ Thiết lập Render',
                children: (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', padding: '12px 8px 0 8px' }}>
                    {/* Images Upload */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.45)', fontWeight: '600', textTransform: 'uppercase' }}>🖼️ Ảnh Phân Cảnh ({imagePaths.length})</span>
                      <Upload
                        accept="image/*"
                        multiple
                        showUploadList={false}
                        beforeUpload={(file, fileList) => {
                          pendingFilesRef.current.push(file);
                          if (uploadTimeoutRef.current) {
                            clearTimeout(uploadTimeoutRef.current);
                          }
                          uploadTimeoutRef.current = setTimeout(() => {
                            if (pendingFilesRef.current.length > 0) {
                              performBatchImageUpload([...pendingFilesRef.current]);
                              pendingFilesRef.current = [];
                            }
                          }, 100);
                          return false;
                        }}
                      >
                        <Button 
                          icon={<UploadCloud size={14} style={{ marginRight: '6px' }} />}
                          style={{ width: '100%', height: '32px', background: '#0d0e12', border: '1px dashed #22252c', fontSize: '12px' }}
                        >
                          Chọn danh sách ảnh phân cảnh
                        </Button>
                      </Upload>

                      {/* Thumbnails grid */}
                      {imagePaths.length > 0 && (
                        <div style={{ 
                          display: 'grid', 
                          gridTemplateColumns: 'repeat(auto-fill, minmax(40px, 1fr))', 
                          gap: '4px', 
                          marginTop: '6px',
                          maxHeight: '120px',
                          overflowY: 'auto',
                          padding: '4px',
                          background: '#0d0e12',
                          borderRadius: '4px',
                          border: '1px solid #22252c'
                        }}>
                          {imagePaths.map((path, idx) => {
                            const basename = path.substring(path.lastIndexOf('/') + 1);
                            const relativeUrl = "/uploads/images/" + encodeURIComponent(basename);
                            return (
                              <div key={idx} style={{ position: 'relative', aspectRatio: '1', borderRadius: '3px', overflow: 'hidden', border: '1px solid #22252c' }}>
                                <img src={relativeUrl} alt={basename} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                                <span style={{ 
                                  position: 'absolute', 
                                  bottom: '1px', 
                                  right: '1px', 
                                  background: 'rgba(0,0,0,0.75)', 
                                  color: '#fff', 
                                  fontSize: '8px', 
                                  padding: '0px 2px', 
                                  borderRadius: '1px',
                                  fontWeight: '600'
                                }}>
                                  {idx + 1}
                                </span>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>

                    {/* Aspect Ratio */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.45)', fontWeight: '600', textTransform: 'uppercase' }}>📐 Tỉ Lệ Khung Hình</span>
                      <Radio.Group 
                        value={resolution} 
                        onChange={(e) => setResolution(e.target.value)} 
                        optionType="button" 
                        buttonStyle="solid"
                        style={{ width: '100%', display: 'flex' }}
                      >
                        <Radio.Button value="Dọc 9:16 (TikTok/Reels)" style={{ flex: 1, fontSize: '10px', textAlign: 'center', height: '32px', lineHeight: '30px', padding: 0 }}>9:16 Dọc</Radio.Button>
                        <Radio.Button value="Ngang 16:9 (YouTube)" style={{ flex: 1, fontSize: '10px', textAlign: 'center', height: '32px', lineHeight: '30px', padding: 0 }}>16:9 Ngang</Radio.Button>
                        <Radio.Button value="Vuông 1:1 (Instagram)" style={{ flex: 1, fontSize: '10px', textAlign: 'center', height: '32px', lineHeight: '30px', padding: 0 }}>1:1 Vuông</Radio.Button>
                      </Radio.Group>
                    </div>

                    {/* Camera zoom / Transition Sliders */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      <div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '2px' }}>
                          <span style={{ color: 'rgba(255,255,255,0.45)', fontWeight: '600' }}>🎥 Camera Motion (zoom/pan)</span>
                          <span style={{ color: '#1677ff', fontWeight: 'bold' }}>{intensity}</span>
                        </div>
                        <Slider 
                          min={0.0} 
                          max={0.15} 
                          step={0.01} 
                          value={intensity} 
                          onChange={(val) => setIntensity(val)} 
                          style={{ margin: '4px 0' }}
                        />
                      </div>

                      <div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '2px' }}>
                          <span style={{ color: 'rgba(255,255,255,0.45)', fontWeight: '600' }}>✨ Transition Duration</span>
                          <span style={{ color: '#1677ff', fontWeight: 'bold' }}>{transitionDur}s</span>
                        </div>
                        <Slider 
                          min={0.2} 
                          max={1.5} 
                          step={0.1} 
                          value={transitionDur} 
                          onChange={(val) => setTransitionDur(val)} 
                          style={{ margin: '4px 0' }}
                        />
                      </div>
                    </div>

                    {/* Fast Preview Toggle */}
                    <div style={{ 
                      display: 'flex', 
                      justifyContent: 'space-between', 
                      alignItems: 'center', 
                      background: '#0d0e12', 
                      padding: '6px 10px', 
                      borderRadius: '4px', 
                      border: '1px solid #22252c',
                      height: '32px',
                      boxSizing: 'border-box'
                    }}>
                      <span style={{ fontSize: '11px', fontWeight: '500', color: 'rgba(255,255,255,0.65)' }}>⚡ Preview Nhanh (360p, 15 FPS)</span>
                      <Switch checked={previewMode} onChange={(checked) => setPreviewMode(checked)} size="small" />
                    </div>
                  </div>
                )
              }
            ]}
          />
        </div>
      </Sider>

      {/* Center Panel: Workspace Timeline Table & Console logs */}
      <Layout className="main-layout">
        {/* Connection Status Header */}
        <Header style={{ 
          height: '56px', 
          lineHeight: '56px', 
          background: '#15171c', 
          borderBottom: '1px solid #22252c', 
          padding: '0 20px', 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center' 
        }}>
          <Text style={{ color: 'rgba(255,255,255,0.45)', fontSize: '12px' }}>Workspace / Subtitle Editor</Text>
          <Space size={6}>
            <Badge status="processing" color="#10b981" />
            <Text style={{ color: '#fff', fontSize: '12px' }}>Thiết bị trực tuyến</Text>
          </Space>
        </Header>

        {/* Workspace Panels */}
        <Content className="main-content" style={{ display: 'flex', flexDirection: 'column', gap: '12px', height: 'calc(100vh - 56px)', overflow: 'hidden' }}>
          {/* Subtitle Timeline Editor */}
          <Card 
            title={
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                <span>Biên tập Subtitle Timeline</span>
                <Space size={8}>
                  {matchedScenes.length > 0 && (
                    <>
                      <Space size={4}>
                        <Button size="small" type="text" style={{ fontSize: '11px', color: 'rgba(255,255,255,0.45)' }} icon={<FileText size={12} />} onClick={() => handleExport('srt')}>SRT</Button>
                        <Button size="small" type="text" style={{ fontSize: '11px', color: 'rgba(255,255,255,0.45)' }} icon={<FileJson size={12} />} onClick={() => handleExport('json')}>JSON</Button>
                        <Button size="small" type="text" style={{ fontSize: '11px', color: 'rgba(255,255,255,0.45)' }} icon={<TableIcon size={12} />} onClick={() => handleExport('csv')}>CSV</Button>
                      </Space>
                      <Button 
                        type="primary" 
                        size="small"
                        icon={<RefreshCw size={12} />} 
                        loading={isSyncing} 
                        onClick={handleSync}
                        style={{ background: '#1677ff', borderColor: '#1677ff', fontSize: '11px', fontWeight: '600' }}
                      >
                        Đồng bộ thay đổi
                      </Button>
                    </>
                  )}
                </Space>
              </div>
            }
            className="flat-card"
            style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
            bodyStyle={{ flex: 1, padding: '8px 12px', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
          >
            {matchedScenes.length === 0 ? (
              <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: 0.35 }}>
                <Space direction="vertical" align="center" size={8}>
                  <Sliders size={32} />
                  <Text style={{ fontSize: '12px' }}>Chưa có dữ liệu phân cảnh. Vui lòng chạy phân tích ở cột trái.</Text>
                </Space>
              </div>
            ) : (
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px', overflow: 'hidden' }}>
                {/* Warnings banner */}
                {timelineWarnings.length > 0 && (
                  <Alert
                    message={`Phát hiện ${timelineWarnings.length} lỗi logic timeline (Đè chéo thời gian hoặc khoảng âm)`}
                    type="warning"
                    showIcon
                    className="compact-alert"
                    style={{ background: 'rgba(250, 173, 20, 0.08)', border: '1px solid rgba(250, 173, 20, 0.25)' }}
                  />
                )}
                
                {/* Antd Table configured for scroll */}
                <Table
                  dataSource={dataSource}
                  columns={columns}
                  pagination={false}
                  size="small"
                  scroll={{ y: 'calc(100vh - 360px)' }}
                />
              </div>
            )}
          </Card>

          {/* Terminal Logs (Fixed height) */}
          <Card 
            title="Tiến trình render (Engine Logs)" 
            className="flat-card" 
            style={{ height: '160px', flexShrink: 0, display: 'flex', flexDirection: 'column' }}
            bodyStyle={{ flex: 1, padding: 8, overflow: 'hidden' }}
          >
            <pre className="flat-console">
              {consoleLogs.map((log, index) => (
                <div key={index} className="flat-console-line">
                  {log}
                </div>
              ))}
              <div ref={consoleEndRef} />
            </pre>
          </Card>
        </Content>
      </Layout>

      {/* Right Panel: Video Preview & Primary Operations (Dedicated Column) */}
      <Sider width={420} className="sider-panel-right" trigger={null} style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
        <div style={{ 
          padding: '12px 16px', 
          borderBottom: '1px solid #22252c', 
          display: 'flex', 
          alignItems: 'center', 
          height: '56px',
          boxSizing: 'border-box',
          flexShrink: 0
        }}>
          <span style={{ color: '#fff', fontWeight: '700', fontSize: '13px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            📺 Màn hình xem trước
          </span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', flex: 1, padding: '16px', gap: '16px', overflow: 'hidden' }}>
          {/* Dynamic Mockup Video Player - Stretches to fill height */}
          <Card 
            bordered={false} 
            style={{ background: '#090a0f', border: '1px solid #22252c', borderRadius: '6px', flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
            bodyStyle={{ padding: '12px 8px', flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', overflow: 'hidden' }}
          >
            <div className="preview-container">
              <div className={`device-mockup ${getResolutionClass()}`}>
                <div className="device-notch" />
                {videoUrl ? (
                  <video key={videoUrl} controls>
                    <source src={videoUrl} type="video/mp4" />
                    Trình duyệt không hỗ trợ.
                  </video>
                ) : (
                  <div className="video-placeholder" style={{ padding: '0 20px', fontSize: '11px' }}>
                    {isRendering ? (
                      <Space direction="vertical" align="center" size={8}>
                        <Progress type="circle" percent={renderProgress} size={36} strokeColor="#1677ff" />
                        <Text style={{ color: 'rgba(255,255,255,0.45)', fontSize: '10px' }}>Đang render...</Text>
                      </Space>
                    ) : (
                      'Chưa có video. Nhấn "Bắt đầu Tạo Video" ở phía dưới.'
                    )}
                  </div>
                )}
              </div>
            </div>
          </Card>

          {/* Action buttons panel below the video player */}
          <div style={{ flexShrink: 0, display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <Button 
              type="primary" 
              icon={<Play size={14} style={{ marginRight: '6px' }} />}
              loading={isRendering}
              onClick={handleRender}
              style={{ width: '100%', height: '38px', background: '#1677ff', borderColor: '#1677ff', fontSize: '13px', fontWeight: '600' }}
            >
              Bắt đầu Tạo Video
            </Button>
            {videoUrl && (
              <Button 
                href={videoUrl}
                download
                icon={<Download size={14} style={{ marginRight: '6px' }} />}
                style={{ width: '100%', height: '34px', fontSize: '12px' }}
              >
                Tải xuống Video
              </Button>
            )}
          </div>
        </div>
      </Sider>
    </Layout>
  );
}

export default function App() {
  return (
    <ConfigProvider
      theme={{
        algorithm: antdTheme.darkAlgorithm,
        token: {
          colorPrimary: '#1677ff',
          colorBgBase: '#0f1012',
          colorBgContainer: '#15171c',
          colorBorder: '#22252c',
          fontFamily: 'Plus Jakarta Sans, Inter, system-ui, sans-serif',
        },
      }}
    >
      <VideoGeneratorApp />
    </ConfigProvider>
  );
}
