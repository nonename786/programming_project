// ==========================================
// 1. 全局变量初始化
// ==========================================
axios.defaults.headers.common['Authorization'] = 'Bearer ' + localStorage.getItem('token');
if(!localStorage.getItem('token')) window.location.href = 'index.html';

const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
let img = new Image();
let sourceImg = null; // 用于造字台回溯

// 画板状态控制
let isDrawing = false, startX, startY;
let currentRect = null; // 单画框及拖拽时的临时框
let currentMultiRects =[]; // 存放多画框模式下的所有框
let markColor = '#8b2929';
let interactionMode = 'rect'; // 'rect', 'multi-rect', 'doodle'

// 卷宗与 PDF 控制
let currentDocId = null;
let pdfDoc = null;
let pageNum = 1;
let pageRendering = false;
let pageNumPending = null;

// 右侧批注档案控制
let allHistoryData = null;
let pageAnnotations =[]; // 保存当前页所有批注
let activeAnnotationId = null; // 当前高亮选中的批注ID
let currentAnnTab = '字'; // 当前选中的体例卡片


// ==========================================
// 2. 页面载入与路由解析
// ==========================================
window.onload = async () => {
    // 隐藏所有弹窗
    document.querySelectorAll('.scroll-modal, .modal-overlay').forEach(el => el.style.display = 'none');
    
    // 检查是否有待办邀请
    fetchInvites();

    const urlParams = new URLSearchParams(window.location.search);
    let targetDocId = urlParams.get('docId');
    // 【关键修复 1】：尝试从网址中获取页码，如果没有才默认是 1
    let targetPageNum = parseInt(urlParams.get('page')) || 1;

    // 逻辑判定：如何恢复阅读进度
    if (!targetDocId) {
        // 场景 A：直接打开网页，没有任何参数，尝试从本地缓存恢复最后一次看的书和页码
        const savedState = localStorage.getItem('last_active_state');
        if (savedState) {
            const state = JSON.parse(savedState);
            targetDocId = state.docId;
            targetPageNum = state.pageNum || 1;
        }
    } else {
        // 场景 B：通过链接进来的（带有 docId）
        // 如果网址里没有明确要求跳到哪一页（比如点击信箱里的“接下信物”），就看看本地有没有这本卷宗的进度
        if (!urlParams.get('page')) {
            const savedState = localStorage.getItem('last_active_state');
            if (savedState) {
                const state = JSON.parse(savedState);
                if (String(state.docId) === String(targetDocId)) {
                    targetPageNum = state.pageNum || 1;
                }
            }
        }
    }

    // 载入卷宗数据
    if (targetDocId) {
        try {
            const res = await axios.get(`/api/collaboration/access/${targetDocId}`);
            const doc = res.data;
            if (doc.file_type === 'application/pdf') {
                loadPdfFromServer(doc.filename, targetPageNum); // 【成功将页码传给渲染器】
            } else {
                loadImgFromServer(doc.filename);
            }
            currentDocId = targetDocId;
        } catch (e) {
            console.error("还原卷宗失败:", e);
        }
    }
};


// ==========================================
// 3. 画板重绘引擎与鼠标事件
// ==========================================

// 核心重绘画布引擎 (支持单框、多框、数据库历史框)
function drawCanvas() {
    if (!img.src) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

    // 1. 绘制历史保存的框
    pageAnnotations.forEach(ann => {
        if (!ann.coordinates) return;
        try {
            const parsed = JSON.parse(ann.coordinates);
            ctx.strokeStyle = ann.mark_color || '#8b2929';
            const isActive = (ann.id === activeAnnotationId);
            
            if (isActive) {
                ctx.lineWidth = 4;
                ctx.fillStyle = 'rgba(255, 215, 0, 0.2)'; // 黄色高亮背景
            } else {
                ctx.lineWidth = 2;
                // 让历史记录也有一层极淡的红色背景，方便辨认
                ctx.fillStyle = 'rgba(139, 41, 41, 0.1)'; 
            }

            if (Array.isArray(parsed)) {
                parsed.forEach(r => {
                    ctx.fillRect(r.x, r.y, r.w, r.h); // 填充半透明底色
                    ctx.strokeRect(r.x, r.y, r.w, r.h);
                });
            } else {
                ctx.fillRect(parsed.x, parsed.y, parsed.w, parsed.h);
                ctx.strokeRect(parsed.x, parsed.y, parsed.w, parsed.h);
            }
        } catch(e){}
    });


    // 2. 绘制多画框模式下已存放的框 (改为实线边框 + 半透明底色)
    currentMultiRects.forEach(rect => {
        ctx.strokeStyle = markColor; // 跟随顶部选中的颜色
        ctx.lineWidth = 2;
        ctx.setLineDash([]); // 强制使用实线  
        
        // 开启透明度，画内部填充色
        ctx.globalAlpha = 0.2; 
        ctx.fillStyle = markColor; 
        ctx.fillRect(rect.x, rect.y, rect.w, rect.h);
        
        // 恢复不透明度，画外边框
        ctx.globalAlpha = 1.0; 
        ctx.strokeRect(rect.x, rect.y, rect.w, rect.h);
    });

    
    // 3. 绘制当前鼠标正在拖拽的框，或者单框模式下画好的框
    if ((interactionMode === 'rect' || interactionMode === 'multi-rect') && currentRect) {
        ctx.strokeStyle = markColor;
        ctx.lineWidth = 2;
        ctx.setLineDash([]); // 强制使用实线
        
        // 开启透明度，画内部填充色
        ctx.globalAlpha = 0.2; 
        ctx.fillStyle = markColor; 
        ctx.fillRect(currentRect.x, currentRect.y, currentRect.w, currentRect.h);
        
        // 恢复不透明度，画外边框
        ctx.globalAlpha = 1.0; 
        ctx.strokeRect(currentRect.x, currentRect.y, currentRect.w, currentRect.h);
    }
}

// 鼠标按下
canvas.addEventListener('mousedown', e => {
    if(!img.src) return;
    isDrawing = true;
    const rect = canvas.getBoundingClientRect();
    startX = (e.clientX - rect.left) * (canvas.width / rect.width);
    startY = (e.clientY - rect.top) * (canvas.height / rect.height);

    // 仅在浏览模式时点击清空高亮
    if (document.getElementById('annotationForm').style.display === 'none') {
        activeAnnotationId = null;
        renderAnnotationList();
        drawCanvas();
    }

    if(interactionMode === 'doodle') {
        ctx.beginPath();
        ctx.moveTo(startX, startY);
        ctx.strokeStyle = markColor;
        ctx.lineWidth = 3;
        ctx.lineCap = 'round';
    }
});

// 鼠标移动
canvas.addEventListener('mousemove', e => {
    if (!isDrawing) return;
    const rect = canvas.getBoundingClientRect();
    const mouseX = (e.clientX - rect.left) * (canvas.width / rect.width);
    const mouseY = (e.clientY - rect.top) * (canvas.height / rect.height);
    
    if (interactionMode === 'rect' || interactionMode === 'multi-rect') {
        currentRect = { x: startX, y: startY, w: mouseX - startX, h: mouseY - startY };
        drawCanvas();
    } else if (interactionMode === 'doodle') {
        ctx.lineTo(mouseX, mouseY);
        ctx.stroke();
    }
});

// 鼠标松开
canvas.addEventListener('mouseup', () => {
    isDrawing = false;
    
    // 如果是多选框，将画好的框推入数组并清空 currentRect 缓冲
    if (interactionMode === 'multi-rect' && currentRect) {
        if (Math.abs(currentRect.w) > 5 && Math.abs(currentRect.h) > 5) {
            currentMultiRects.push(currentRect);
        }
        currentRect = null; 
        drawCanvas();
    }
});

// 工具条动作
function setInteractionMode(mode) {
    interactionMode = mode;
    canvas.style.cursor = mode === 'doodle' ? 'url("https://cur.cursors-4u.net/nature/nat-10/nat984.cur"), auto' : 'crosshair';
}
function setColor(color, el) {
    markColor = color;
    document.querySelectorAll('.color-dot').forEach(d => d.classList.remove('active'));
    el.classList.add('active');
}
function clearMultiRects() {
    currentMultiRects =[];
    currentRect = null;
    drawCanvas();
}


// ==========================================
// 4. 右侧列表与新增表单逻辑
// ==========================================

async function fetchAnnotationsForPage(docId, page) {
    try {
        const res = await axios.get(`/api/annotations/${docId}/page/${page}`);
        pageAnnotations = res.data.data;
        renderAnnotationList();
        drawCanvas();
    } catch(e) { console.error("获取批注失败", e); }
}

function switchAnnTab(type) {
    currentAnnTab = type;
    document.querySelectorAll('.ann-tabs button').forEach(btn => btn.classList.remove('active'));
    document.getElementById('tab-' + type).classList.add('active');
    renderAnnotationList();
}

function renderAnnotationList() {
    const listDiv = document.getElementById('annotationList');
    listDiv.innerHTML = '';
    
    const filtered = pageAnnotations.filter(a => a.mark_type === currentAnnTab);
    if (filtered.length === 0) {
        listDiv.innerHTML = '<p style="text-align:center; color:#999; margin-top:20px;">本页暂无此体例记录</p>';
        return;
    }

    filtered.forEach(ann => {
        const isActive = ann.id === activeAnnotationId ? 'active' : '';
        const thumbHtml = ann.image_data ? `<img src="${ann.image_data}" style="width:45px; height:45px; object-fit:cover; border:1px solid var(--border-color); border-radius:3px; margin-right:10px; flex-shrink:0;">` : '';

        listDiv.innerHTML += `
            <div class="ann-item ${isActive}" onclick="highlightAnnotation(${ann.id})" style="display:flex; align-items:center;">
                ${thumbHtml}
                <div style="flex:1; min-width:0;">
                    <div style="font-size:12px; color:var(--primary-red); margin-bottom:2px;">
                        <strong>[${ann.status}]</strong> ${new Date(ann.created_at).toLocaleTimeString()}
                    </div>
                    <div style="font-weight:bold; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">原: ${ann.original_text || '（空）'}</div>
                    <div style="color:#444; font-size:13px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">简: ${ann.simplified_text || '（空）'}</div>
                </div>
            </div>
        `;
    });
}

function highlightAnnotation(id) {
    activeAnnotationId = id;
    renderAnnotationList();
    drawCanvas();
}

function startNewAnnotation() {
    try {
        const multiRects = (typeof currentMultiRects !== 'undefined' && currentMultiRects) ? currentMultiRects :[];
        const targetRect = multiRects.length > 0 ? multiRects[0] : currentRect;
        
        if (!targetRect || typeof targetRect.w === 'undefined') {
            return alert("请先在左侧古籍画面上拖拽出一个方框（或多个）作为目标！");
        }
        
        const drawW = Math.abs(targetRect.w);
        const drawH = Math.abs(targetRect.h);
        if (drawW < 5 || drawH < 5) return alert("框选区域太小，请重新画框！");

        document.getElementById('annotationForm').style.display = 'block';
        if (document.getElementById('p_type')) document.getElementById('p_type').value = currentAnnTab;

        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = drawW;
        tempCanvas.height = drawH;
        const drawX = Math.min(targetRect.x, targetRect.x + targetRect.w);
        const drawY = Math.min(targetRect.y, targetRect.y + targetRect.h);
        
        tempCanvas.getContext('2d').drawImage(img, drawX, drawY, drawW, drawH, 0, 0, drawW, drawH);
        
        const imgEl = document.getElementById('formCroppedImg');
        if (imgEl) {
            window.currentCroppedBase64 = tempCanvas.toDataURL('image/jpeg', 0.8); 
            imgEl.src = window.currentCroppedBase64;
            imgEl.style.display = 'block';
        }
    } catch (e) {
        alert("打开表单失败: " + e.message);
    }
}

function closeAnnotationForm() {
    document.getElementById('annotationForm').style.display = 'none';
}


// ==========================================
// 5. AI 与落笔保存
// ==========================================

async function aiRecognize() {
    try {
        const multiRects = (typeof currentMultiRects !== 'undefined' && currentMultiRects) ? currentMultiRects :[];
        const targetRect = multiRects.length > 0 ? multiRects[0] : currentRect;

        if (!targetRect) return alert('请先在古籍上框选要识别的区域！');
        if (!img.src) return alert('请先载入古籍图片！');

        const resultDisplay = document.getElementById('ocrResult');
        if(resultDisplay) resultDisplay.innerText = "夫子正在研读字迹，请稍候...";

        const tempCanvas = document.createElement('canvas');
        const drawW = Math.abs(targetRect.w);
        const drawH = Math.abs(targetRect.h);
        if (drawW < 5 || drawH < 5) return alert("框选太小！");

        tempCanvas.width = drawW;
        tempCanvas.height = drawH;
        const drawX = Math.min(targetRect.x, targetRect.x + targetRect.w);
        const drawY = Math.min(targetRect.y, targetRect.y + targetRect.h);

        tempCanvas.getContext('2d').drawImage(img, drawX, drawY, drawW, drawH, 0, 0, drawW, drawH);
        const base64Image = tempCanvas.toDataURL('image/jpeg', 0.9);

        const res = await axios.post('/api/ocr/ai-recognize', { image: base64Image });
        const aiText = res.data.text;
        
        if(resultDisplay) resultDisplay.innerText = aiText;
        if(document.getElementById('p_simplified')) document.getElementById('p_simplified').value = aiText; 
        if(document.getElementById('p_original')) document.getElementById('p_original').value = aiText; 

    } catch (err) {
        const detail = err.response?.data?.details || err.message;
        if(document.getElementById('ocrResult')) document.getElementById('ocrResult').innerText = "识读失败：" + detail;
        alert("识读失败: " + detail);
    }
}

async function saveAnnotation() {
    try {
        const multiRects = (typeof currentMultiRects !== 'undefined' && currentMultiRects) ? currentMultiRects :[];
        const targetRect = multiRects.length > 0 ? multiRects[0] : currentRect;
        
        if (!targetRect) return alert('请先框选区域！');
        if (!currentDocId) return alert('请先载入文件再做保存！');

        let aiText = '';
        const qwenEl = document.getElementById('qwenContent');
        if (qwenEl && !qwenEl.innerText.includes("正在加载")) {
            aiText = qwenEl.innerText;
        }

        const coordsToSave = multiRects.length > 0 ? multiRects : currentRect;

        const data = {
            document_id: currentDocId,
            page_number: typeof pageNum !== 'undefined' ? pageNum : 1,
            mark_type: document.getElementById('p_type') ? document.getElementById('p_type').value : '字',
            mark_color: typeof markColor !== 'undefined' ? markColor : '#8b2929', 
            original_text: document.getElementById('p_original') ? document.getElementById('p_original').value : '',
            simplified_text: document.getElementById('p_simplified') ? document.getElementById('p_simplified').value : '',
            meaning: document.getElementById('p_meaning') ? document.getElementById('p_meaning').value : '',
            notes: document.getElementById('p_notes') ? document.getElementById('p_notes').value : '',
            ai_analysis: aiText,
            coordinates: JSON.stringify(coordsToSave), 
            status: document.getElementById('p_status') ? document.getElementById('p_status').value : '待审',
            image_data: window.currentCroppedBase64 || null 
        };

        await axios.post('/api/annotations', data);
        alert('✅ 已成功录入库中！');
        
        // 清空表单
        ['p_original','p_simplified','p_meaning','p_notes'].forEach(id => {
            if(document.getElementById(id)) document.getElementById(id).value = '';
        });
        
        clearMultiRects(); 
        closeAnnotationForm();
        fetchAnnotationsForPage(currentDocId, typeof pageNum !== 'undefined' ? pageNum : 1);

    } catch (e) {
        alert('保存失败：' + (e.response?.data?.error || e.message));
    }
}


// ==========================================
// 6. 协作系统信箱控制
// ==========================================
async function fetchInvites() {
    try {
        const res = await axios.get('/api/collaboration/my-invites');
        const invites = res.data;
        const badge = document.getElementById('msgBadge');
        if(!badge) return;
        
        if (invites.length > 0) {
            badge.style.display = 'inline-block';
            badge.innerText = invites.length;
        } else {
            badge.style.display = 'none';
        }
        
        const listDiv = document.getElementById('invitesList');
        listDiv.innerHTML = '';
        if(invites.length === 0) {
            listDiv.innerHTML = '<p style="text-align:center; color:#999;">暂无未读信件</p>';
            return;
        }

        invites.forEach(inv => {
            listDiv.innerHTML += `
                <div style="border: 1px solid var(--primary-red); padding: 10px; border-radius: 4px; background: rgba(255,255,255,0.6);">
                    <p style="margin:0 0 10px 0;"><strong>${inv.sender_name}</strong> 邀请你共编《${inv.doc_title}》</p>
                    <button class="red-seal" onclick="acceptInvite(${inv.id}, ${inv.doc_id})">接下信物 (进入)</button>
                </div>
            `;
        });
    } catch (e) {}
}

function toggleInvitesModal() {
    const modal = document.getElementById('invitesModal');
    const overlay = document.getElementById('modalOverlay') || document.getElementById('historyOverlay');
    if (modal.style.display === 'flex' || modal.style.display === 'block') {
        modal.style.display = 'none';
        if(overlay) overlay.style.display = 'none';
    } else {
        modal.style.display = 'flex';
        modal.style.flexDirection = 'column';
        if(overlay) overlay.style.display = 'block';
        fetchInvites();
    }
}

async function sendInvite() {
    const username = document.getElementById('inviteUsername').value;
    if (!username) return alert("请填入户籍名号！");
    if (!currentDocId) return alert("请先载入卷宗！");
    try {
        const res = await axios.post('/api/collaboration/invite', { username, document_id: currentDocId });
        alert(res.data.message);
        document.getElementById('inviteUsername').value = '';
    } catch(e) { alert(e.response?.data?.error || "发送失败"); }
}

async function acceptInvite(inviteId, docId) {
    try {
        await axios.post(`/api/collaboration/accept/${inviteId}`);
        alert("信物已接，即刻启程！");
        // 【关键修复 3】：不再强制写死第1页，直接利用网址进入。
        // 前面的 onload 系统会自动帮你接管，如果看过就恢复进度，没看过就默认第1页
        window.location.href = `editor.html?docId=${docId}`;
    } catch(e) { alert("接受失败"); }
}

// 生成邀请链接弹窗
function openCollabModal() {
    if (!currentDocId) return alert("请先载入一份古籍再邀请协作。");
    let host = window.location.host; 
    let protocol = window.location.protocol;
    
    // 【关键修复 4】：分享链接给同僚时，把“当前正在阅读的页码”也带上！
    // 这样别人打开链接时，看到的就是你正在看的这一页。
    const currentPage = typeof pageNum !== 'undefined' ? pageNum : 1;
    const shareUrl = `${protocol}//${host}/editor.html?docId=${currentDocId}&page=${currentPage}`;
    
    document.getElementById('shareLink').innerText = shareUrl;
    const overlay = document.getElementById('modalOverlay');
    if (overlay) overlay.style.display = 'block';
    const modal = document.getElementById('collabModal');
    modal.style.display = 'flex';
    modal.style.flexDirection = 'column';
}
function closeCollab() {
    if (document.getElementById('modalOverlay')) document.getElementById('modalOverlay').style.display = 'none';
    document.getElementById('collabModal').style.display = 'none';
}
function copyShareLink() {
    navigator.clipboard.writeText(document.getElementById('shareLink').innerText).then(() => {
        alert("邀请链接已复制到剪贴板！");
    });
}


// ==========================================
// 7. 图片与 PDF 文件载入控制
// ==========================================

function loadImgFromServer(filename) {
    img = new Image();
    img.src = `/api/upload/file/${filename}`;
    img.onload = () => {
        canvas.width = img.width;
        canvas.height = img.height;
        ctx.drawImage(img, 0, 0);
        fetchAnnotationsForPage(currentDocId, 1); // 加载完后拉取批注
    };
}

document.getElementById('fileInput').addEventListener('change', async function(e) {
    const file = e.target.files[0];
    if(!file) return;

    const reader = new FileReader();
    reader.onload = function(event) {
        localStorage.setItem('temp_character_img', event.target.result);
        const tempImg = new Image();
        tempImg.onload = () => {
            const panel = document.querySelector('.left-panel');
            const maxWidth = panel.clientWidth - 40;  
            const maxHeight = panel.clientHeight - 60; 
            let scale = Math.min(maxWidth / tempImg.width, maxHeight / tempImg.height);
            if (scale > 1) scale = 1; 

            canvas.width = tempImg.width * scale;
            canvas.height = tempImg.height * scale;
            ctx.drawImage(tempImg, 0, 0, canvas.width, canvas.height);

            img.onload = null; 
            img.src = canvas.toDataURL('image/jpeg', 1.0);
            sourceImg = img; 
            
            if (document.getElementById('pdfControls')) document.getElementById('pdfControls').style.display = 'none';
        }
        tempImg.src = event.target.result;
    };
    reader.readAsDataURL(file);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', file.name || '佚名古籍'); 
    
    try {
        const res = await axios.post('/api/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
        currentDocId = res.data.document.id;
        saveEditorState(); 
        fetchAnnotationsForPage(currentDocId, 1); // 上传完建档并拉取
    } catch(err) {
        alert('上传建档失败: ' + err.message);
    }
});


pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.4.120/pdf.worker.min.js';
document.getElementById('pdfInput').addEventListener('change', async function(e) {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', file.name);
    try {
        const res = await axios.post('/api/upload', formData);
        currentDocId = res.data.document.id;
        saveEditorState(); 
    } catch(err) { console.error("PDF 上传失败"); }

    const reader = new FileReader();
    reader.onload = function() {
        const typedarray = new Uint8Array(this.result);
        pdfjsLib.getDocument(typedarray).promise.then(function(pdfDoc_) {
            pdfDoc = pdfDoc_;
            if (document.getElementById('pdfControls')) document.getElementById('pdfControls').style.setProperty('display', 'flex', 'important');
            document.getElementById('pageInfo').textContent = `第 1 / ${pdfDoc.numPages} 页`;
            pageNum = 1;
            renderPage(pageNum);
        });
    };
    reader.readAsArrayBuffer(file);
});

//微微一笑，可以啊，你用的是什么关键词检索啊，我们可以一起讨论一下

//林晓起，我和自选真的只是在讨论学术问题。图书馆里有监控，你可以去查。请你冷静一点
async function loadPdfFromServer(filename, pageToRender) {
    try {
        const response = await axios.get(`/api/upload/file/${filename}`, { responseType: 'arraybuffer' });
        const typedarray = new Uint8Array(response.data);
        pdfjsLib.getDocument(typedarray).promise.then(function(pdfDoc_) {
            pdfDoc = pdfDoc_;
            if(document.getElementById('pdfControls')) document.getElementById('pdfControls').style.display = 'flex';
            pageNum = pageToRender || 1;
            renderPage(pageNum);
        });
    } catch (e) {
        console.error("加载PDF流失败", e);
    }
}

function renderPage(num) {
    pageRendering = true;
    pdfDoc.getPage(num).then(function(page) {
        const viewport = page.getViewport({ scale: 1.5 });
        canvas.height = viewport.height;
        canvas.width = viewport.width;

        const renderContext = { canvasContext: ctx, viewport: viewport };
        page.render(renderContext).promise.then(function() {
            pageRendering = false;
            setTimeout(() => {
                try {
                    const currentPageData = canvas.toDataURL('image/jpeg', 0.6);
                    img = new Image();
                    img.src = currentPageData;
                    localStorage.setItem('temp_character_img', currentPageData);
                    pageNum = num; 
                    saveEditorState(); 
                    
                    fetchAnnotationsForPage(currentDocId, pageNum); // 【关键】：渲染完成去拉取当前页画框
                } catch (e) {
                    localStorage.setItem('temp_character_img', canvas.toDataURL('image/jpeg', 0.4));
                }
            }, 100);

            document.getElementById('pageInfo').textContent = `第 ${num} / ${pdfDoc.numPages} 页`;
            if (pageNumPending !== null) {
                renderPage(pageNumPending);
                pageNumPending = null;
            }
        });
    });
}
function queueRenderPage(num) {
    if (pageRendering) pageNumPending = num;
    else renderPage(num);
}
function prevPage() { if (pageNum <= 1) return; pageNum--; queueRenderPage(pageNum); }
function nextPage() { if (pageNum >= pdfDoc.numPages) return; pageNum++; queueRenderPage(pageNum); }
function jumpToPage() {
    const input = document.getElementById('jumpPageInput');
    const targetPage = parseInt(input.value, 10);
    if (isNaN(targetPage) || targetPage < 1 || targetPage > pdfDoc.numPages) return alert("页码无效！");
    pageNum = targetPage;
    queueRenderPage(pageNum);
    input.value = '';
}


// ==========================================
// 8. 其他：历史档案、AI解析、XML导出
// ==========================================
function saveEditorState() {
    localStorage.setItem('last_active_state', JSON.stringify({ docId: currentDocId, pageNum: pageNum, isPdf: pdfDoc !== null }));
}

async function qwenAnalyze() {
    let text = document.getElementById('p_simplified') ? document.getElementById('p_simplified').value : "";
    if (!text || text.trim() === "") text = document.getElementById('p_original') ? document.getElementById('p_original').value : "";
    if(!text || text === "AI 已自动转化简体" || text.trim() === "") return alert("请先识读或输入文字！");

    document.getElementById('modalOverlay').style.display = 'block';
    document.getElementById('scrollModal').style.display = 'block';
    document.getElementById('qwenContent').innerText = "正在研读卷宗，请稍候...";

    try {
        const res = await axios.post('/api/qwen/analyze', { text });
        document.getElementById('qwenContent').innerHTML = res.data.analysis.replace(/\n/g, '<br>');
    } catch (err) {
        document.getElementById('qwenContent').innerText = "抱歉，夫子今日抱恙，无法讲解。";
    }
}
function closeScroll() {
    if(document.getElementById('modalOverlay')) document.getElementById('modalOverlay').style.display = 'none';
    if(document.getElementById('scrollModal')) document.getElementById('scrollModal').style.display = 'none';
}

async function toggleHistoryModal() {
    const modal = document.getElementById('historyModal');
    let overlay = document.getElementById('historyOverlay') || document.getElementById('modalOverlay');
    if (modal.style.display === 'flex' || modal.style.display === 'block') {
        modal.style.display = 'none';
        if(overlay) overlay.style.display = 'none';
    } else {
        modal.style.display = 'flex';
        modal.style.flexDirection = 'column'; 
        if(overlay) overlay.style.display = 'block';
        document.getElementById('historyDetail').innerHTML = '<p style="color:#999; text-align:center; margin-top:50px;">请在左侧点击一条记录以查看详情</p>';
        await fetchHistory(); 
    }
}

async function fetchHistory() {
    try {
        const res = await axios.get('/api/history/all');
        allHistoryData = res.data;
        showHistoryTab('ann'); 
    } catch (err) {
        alert("调取历史失败");
    }
}

function showHistoryTab(type) {
    const list = document.getElementById('historyList');
    list.innerHTML = "";
    document.getElementById('historyDetail').innerHTML = '<p style="color:#999; text-align:center; margin-top:50px;">请在左侧点击查看详情</p>';
    document.getElementById('tab-ann').classList.remove('active');
    document.getElementById('tab-char').classList.remove('active');
    document.getElementById('tab-' + type).classList.add('active');
    
    if (type === 'ann') {
        if (allHistoryData.annotations.length === 0) return list.innerHTML = "<p style='padding:10px;'>暂无识读批注记录</p>";
        allHistoryData.annotations.forEach((item, index) => {
            list.innerHTML += `
                <div class="history-item" onclick="showHistoryDetail('ann', ${index})" style="border-bottom:1px solid #eee; padding:10px; display:flex; justify-content:space-between; align-items:center; cursor:pointer;">
                    <div style="flex:1">
                        <strong style="color: #8b2929;">[${item.doc_title || '未知卷宗'}]</strong><br>
                        <strong>原文：</strong>${item.original_text ? item.original_text.substring(0, 15) : '无'}...<br>
                    </div>
                    <button onclick="deleteHistory(event, 'annotation', ${item.id})" style="color:red; border-color:red; font-size:12px;">抹除</button>
                </div>`;
        });
    } else if (type === 'char') {
        if (allHistoryData.characters.length === 0) return list.innerHTML = "<p style='padding:10px;'>暂无造字记录</p>";
        allHistoryData.characters.forEach((item, index) => {
            list.innerHTML += `
                <div class="history-item" onclick="showHistoryDetail('char', ${index})" style="border-bottom:1px solid #eee; padding:10px; display:flex; justify-content:space-between; align-items:center; cursor:pointer;">
                    <div style="flex:1">
                        <strong>字：</strong>${item.character_name || '未命名'} | <strong>编码：</strong>${item.unicode_code}<br>
                    </div>
                    <button onclick="deleteHistory(event, 'character', ${item.id})" style="color:red; border-color:red; font-size:12px;">抹除</button>
                </div>`;
        });
    }
}

function showHistoryDetail(type, index) {
    const detail = document.getElementById('historyDetail');
    const item = type === 'ann' ? allHistoryData.annotations[index] : allHistoryData.characters[index];
    if (!item) return;

    let defaultImg = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='100' height='100'><rect width='100%' height='100%' fill='%23f4ecd8'/><text x='50%' y='50%' dominant-baseline='middle' text-anchor='middle' font-size='14' fill='%238b2929'>无截图</text></svg>";
    let imgSrc = item.image_data || item.character_image || item.image_url || defaultImg;

    if (type === 'ann') {
        detail.innerHTML = `
            <h3 style="margin-top:0; border-bottom:1px dashed var(--primary-red); padding-bottom:10px; color:var(--primary-red);">批注详细阅览</h3>
            <div style="text-align:center; margin-bottom:15px;"><img src="${imgSrc}" style="max-width:100%; max-height:180px; border:2px solid var(--border-color); border-radius:4px;"></div>
            <p><strong>卷宗：</strong> ${item.doc_title || '未知'} ${item.page_number ? `(第 ${item.page_number} 页)` : ''}</p>
            <p><strong>原文：</strong> ${item.original_text || '暂无'}</p>
            <p><strong>简体：</strong> ${item.simplified_text || '暂无'}</p>
            <p><strong>字义：</strong> ${item.meaning || '暂无'}</p>
            <p><strong>注解：</strong> ${item.notes || '暂无'}</p>
            <button class="red-seal" style="width:100%; margin-top:15px;" onclick="jumpToHistoryPage(${item.document_id}, ${item.page_number || 1})">🚀 跳转至此页阅览</button>
        `;
    } else {
        detail.innerHTML = `
            <h3 style="margin-top:0; border-bottom:1px dashed var(--primary-red); padding-bottom:10px; color:var(--primary-red);">造字详细阅览</h3>
            <div style="text-align:center; margin-bottom:15px;"><img src="${imgSrc}" style="max-width:100%; max-height:180px;"></div>
            <p><strong>字符名：</strong> ${item.character_name || '暂无'}</p>
            <p><strong>编码：</strong> ${item.unicode_code || '暂无'}</p>
        `;
    }
}

function jumpToHistoryPage(docId, page) {
    toggleHistoryModal();
    localStorage.setItem('last_active_state', JSON.stringify({ docId: docId, pageNum: page, isPdf: true })); 
    //window.location.href = `editor.html?docId=${docId}`;
    window.location.href = `editor.html?docId=${docId}&page=${page}`;
}

async function deleteHistory(event, type, id) {
    event.stopPropagation(); 
    if (!confirm("确定要永久抹除此条记录吗？")) return;
    try {
        await axios.delete(`/api/history/${type}/${id}`);
        alert("已成功抹除。");
        document.getElementById('historyDetail').innerHTML = '';
        await fetchHistory(); 
    } catch (err) { alert("删除失败"); }
}

async function exportXML() {
    try {
        const token = localStorage.getItem('token');
        if (!token) return alert('请先登录！');
        alert('正在生成全库XML，请稍候...');
        const response = await axios.get('/api/export/all', { headers: { 'Authorization': 'Bearer ' + token }, responseType: 'blob' });
        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `古籍档案_${new Date().toLocaleDateString().replace(/\//g, '-')}.xml`);
        document.body.appendChild(link); link.click(); link.remove(); window.URL.revokeObjectURL(url);
    } catch (error) { alert('导出失败'); }
}