        // 当前分类
        let currentCategory = window.AppConfig.defaultCategory;
        let showCategory = window.AppConfig.defaultCategory === 'all' || window.AppConfig.defaultCategory === '全部词汇';
        let searchTimeout = null;

        // 登录状态
        let isLoggedIn = window.AppConfig.isLoggedIn;

        // 音频播放
        let currentAudio = null;
        
        // 朗读单词（请求后端实时生成）
        // 切换侧边栏显示
        function toggleSidebar() {
            const sidebar = document.querySelector('.sidebar');
            const overlay = document.getElementById('sidebarOverlay');
            if (sidebar && overlay) {
                sidebar.classList.toggle('show');
                overlay.classList.toggle('show');
            }
        }
        
        function speak(word, accent, btn) {
            // 停止之前的播放
            if (currentAudio) {
                currentAudio.pause();
                currentAudio.currentTime = 0;
            }
            
            // 添加加载状态
            let loadingInterval = null;
            if (btn) {
                btn.dataset.original = btn.innerHTML;
                btn.classList.add('speak-loading');
                
                // ... 动画
                let dotCount = 1;
                btn.innerHTML = '.'.repeat(dotCount);
                loadingInterval = setInterval(() => {
                    dotCount = dotCount >= 3 ? 1 : dotCount + 1;
                    btn.innerHTML = '.'.repeat(dotCount);
                }, 400);
            }
            
            const audioUrl = '/api/speak?word=' + encodeURIComponent(word) + '&accent=' + accent;
            
            currentAudio = new Audio(audioUrl);
            
            // 清除加载状态的函数
            function clearLoading() {
                if (btn && loadingInterval) {
                    clearInterval(loadingInterval);
                    loadingInterval = null;
                    btn.classList.remove('speak-loading');
                    btn.innerHTML = btn.dataset.original || '🔊';
                }
            }
            
            currentAudio.addEventListener('canplaythrough', function() {
                clearLoading();
            });
            
            currentAudio.addEventListener('error', function() {
                clearLoading();
                fallbackSpeak(word, accent);
            });
            
            currentAudio.play().catch(e => {
                console.error('播放失败:', e);
                clearLoading();
                // 如果播放失败，回退到Web Speech API
                fallbackSpeak(word, accent);
            });
        }
        
        // 备用：Web Speech API
        function fallbackSpeak(word, accent) {
            if (!('speechSynthesis' in window)) {
                alert('音频播放失败');
                return;
            }
            
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(word);
            utterance.lang = accent === 'british' ? 'en-GB' : 'en-US';
            utterance.rate = 0.9;
            window.speechSynthesis.speak(utterance);
        }

        // 加载分类词汇
        // 刷新左侧分类数量
        function refreshCategoryCounts() {
            fetch('/api/categories')
                .then(response => response.json())
                .then(categories => {
                    // 更新全部词汇的数量
                    const totalCount = categories.reduce((sum, cat) => sum + cat.count, 0);
                    const allItem = document.querySelector('.category-item[data-category="all"] .category-count');
                    if (allItem) {
                        allItem.textContent = totalCount;
                    }
                    
                    // 更新每个分类的数量
                    categories.forEach(cat => {
                        const item = document.querySelector(`.category-item[data-category="${cat.name}"] .category-count`);
                        if (item) {
                            item.textContent = cat.count;
                        }
                    });
                    
                    // 更新顶部统计
                    const wordCountEl = document.getElementById('wordCount');
                    if (wordCountEl && currentCategory === 'all') {
                        wordCountEl.textContent = '共 ' + totalCount + ' 个词汇';
                    }
                })
                .catch(error => {
                    console.error('刷新分类数量失败:', error);
                });
        }

        function loadCategory(category) {
            currentCategory = category;
            showCategory = category === 'all' || category === '全部词汇';
            
            // 更新选中状态
            document.querySelectorAll('.category-item').forEach(item => {
                item.classList.remove('active');
                if (item.dataset.category === category) {
                    item.classList.add('active');
                }
            });
            
            // 更新标题
            const categoryName = category === 'all' ? '全部词汇' : category;
            document.getElementById('currentCategory').textContent = categoryName;
            
            // 显示加载状态
            const wordGrid = document.getElementById('wordGrid');
            wordGrid.innerHTML = '<div class="loading">加载中</div>';
            
            // 请求数据
            let url;
            if (category === 'all') {
                url = '/api/all';
            } else {
                url = '/api/category?name=' + encodeURIComponent(category);
            }
            
            fetch(url)
                .then(response => response.json())
                .then(words => {
                    renderWords(words);
                    document.getElementById('wordCount').textContent = '共 ' + words.length + ' 个词汇';
                })
                .catch(error => {
                    console.error('加载失败:', error);
                    wordGrid.innerHTML = '<div class="loading">加载失败，请刷新重试</div>';
                });
        }

        // 搜索词汇
        function searchWords(keyword) {
            if (!keyword.trim()) {
                // 搜索为空时回到当前分类
                loadCategory(currentCategory);
                return;
            }
            
            // 更新标题
            document.getElementById('currentCategory').textContent = '搜索: "' + keyword + '"';
            showCategory = true; // 搜索时显示分类标签
            
            // 显示加载状态
            const wordGrid = document.getElementById('wordGrid');
            wordGrid.innerHTML = '<div class="loading">搜索中</div>';
            
            // 请求搜索
            fetch('/api/search?q=' + encodeURIComponent(keyword))
                .then(response => response.json())
                .then(words => {
                    renderWords(words);
                    document.getElementById('wordCount').textContent = '找到 ' + words.length + ' 个词汇';
                })
                .catch(error => {
                    console.error('搜索失败:', error);
                    wordGrid.innerHTML = '<div class="loading">搜索失败，请重试</div>';
                });
        }

        // 渲染单词卡片
        function renderWords(words) {
            const wordGrid = document.getElementById('wordGrid');
            
            if (words.length === 0) {
                wordGrid.innerHTML = '<div class="loading">没有找到相关词汇</div>';
                return;
            }
            
            let html = '';
            words.forEach(item => {
                const encodedWord = encodeURIComponent(item.english_word);
                html += `
                <div class="word-card">
                    <div class="word-card-header ${showCategory ? 'has-category' : ''}">
                        <div class="word-english">${item.english_word}</div>
                        ${showCategory ? `<div class="word-category">${item.Category}</div>` : ''}
                    </div>
                    <div class="word-phonetics">
                        <div class="phonetic-row">
                            <span class="phonetic-label">英式发音</span>
                            <span class="phonetic-text">${item.british_phonetic}</span>
                            <span class="word-speak" onclick="speak('${item.english_word}', 'british')" title="点击朗读">🔊</span>
                        </div>
                        <div class="phonetic-row">
                            <span class="phonetic-label">美式发音</span>
                            <span class="phonetic-text">${item.american_phonetic}</span>
                            <span class="word-speak" onclick="speak('${item.english_word}', 'american')" title="点击朗读">🔊</span>
                        </div>
                    </div>
                    <div class="word-definition">${item.chinese_definition}</div>
                    <div class="word-actions">
                        <a class="word-btn" href="https://dict.youdao.com/w/${encodedWord}" target="_blank">📖 有道</a>
                        <a class="word-btn" href="https://www.iciba.com/word?w=${encodedWord}" target="_blank">📚 词霸</a>
                        ${isLoggedIn ? `<button class="word-btn ai-example-btn" data-word="${item.english_word}" data-category="${item.Category}">🤖 AI例句</button>` : ''}
                    </div>
                    ${isLoggedIn ? `
                    <div class="word-actions admin-actions" style="padding-top: 8px; border-top: none;">
                        <button class="word-btn word-btn-edit" onclick="editWord(${item.id})">✏️ 编辑</button>
                        <button class="word-btn word-btn-delete" onclick="deleteWord(${item.id}, '${item.english_word}')">🗑️ 删除</button>
                    </div>
                    ` : ''}
                </div>
                `;
            });
            
            wordGrid.innerHTML = html;
            
            // 给AI例句按钮添加点击事件
            if (isLoggedIn) {
                document.querySelectorAll('.ai-example-btn').forEach(btn => {
                    btn.addEventListener('click', function() {
                        const word = this.dataset.word;
                        const category = this.dataset.category;
                        openExampleModal(word, category);
                    });
                });
            }
        }

        // 搜索框事件
        document.getElementById('searchInput').addEventListener('input', function(e) {
            clearTimeout(searchTimeout);
            const keyword = e.target.value;
            
            // 延迟搜索，避免频繁请求
            searchTimeout = setTimeout(() => {
                searchWords(keyword);
            }, 300);
        });

        // 回车搜索
        document.getElementById('searchInput').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                searchWords(e.target.value);
            }
        });

        // ==================== 管理员功能 ====================
        let editingWordId = null;
        let deletingWordId = null;

        // 编辑单词
        function editWord(id) {
            editingWordId = id;
            
            // 获取单词详情
            fetch('/api/admin/word/' + id)
                .then(res => res.json())
                .then(word => {
                    if (word.error) {
                        showToast(word.error, 'error');
                        return;
                    }
                    
                    // 加载分类选项
                    loadCategoryOptions().then(() => {
                        document.getElementById('editCategory').value = word.category_name;
                    });
                    
                    document.getElementById('editEnglish').value = word.english_word;
                    document.getElementById('editBritish').value = word.british_phonetic || '';
                    document.getElementById('editAmerican').value = word.american_phonetic || '';
                    document.getElementById('editDefinition').value = word.chinese_definition || '';
                    
                    document.getElementById('editModalTitle').textContent = '编辑单词';
                    document.getElementById('editModal').classList.add('show');
                })
                .catch(err => {
                    showToast('加载失败: ' + err.message, 'error');
                });
        }

        // 删除单词
        function deleteWord(id, word) {
            deletingWordId = id;
            document.getElementById('deleteWordName').textContent = word;
            document.getElementById('deleteModal').classList.add('show');
        }

        // 保存单词
        function saveWord() {
            const category = document.getElementById('editCategory').value;
            const english = document.getElementById('editEnglish').value.trim();
            const british = document.getElementById('editBritish').value.trim();
            const american = document.getElementById('editAmerican').value.trim();
            const definition = document.getElementById('editDefinition').value.trim();
            
            if (!english) {
                showToast('英文单词不能为空', 'error');
                return;
            }
            
            if (!category) {
                showToast('请选择分类', 'error');
                return;
            }
            
            const data = {
                id: editingWordId,
                category_name: category,
                english_word: english,
                british_phonetic: british,
                american_phonetic: american,
                chinese_definition: definition
            };
            
            fetch('/api/admin/word', {
                method: editingWordId ? 'PUT' : 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            })
            .then(res => res.json())
            .then(result => {
                if (result.success) {
                    showToast('保存成功', 'success');
                    closeEditModal();
                    // 刷新分类数量
                    refreshCategoryCounts();
                    // 重新加载当前列表
                    if (currentCategory) {
                        loadCategory(currentCategory);
                    } else {
                        searchWords(document.getElementById('searchInput').value);
                    }
                } else {
                    showToast(result.message || '保存失败', 'error');
                }
            })
            .catch(err => {
                showToast('保存失败: ' + err.message, 'error');
            });
        }

        // 确认删除
        function confirmDelete() {
            fetch('/api/admin/word', {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: deletingWordId })
            })
            .then(res => res.json())
            .then(result => {
                if (result.success) {
                    showToast('删除成功', 'success');
                    closeDeleteModal();
                    // 刷新分类数量
                    refreshCategoryCounts();
                    // 重新加载当前列表
                    if (currentCategory) {
                        loadCategory(currentCategory);
                    } else {
                        searchWords(document.getElementById('searchInput').value);
                    }
                } else {
                    showToast(result.message || '删除失败', 'error');
                }
            })
            .catch(err => {
                showToast('删除失败: ' + err.message, 'error');
            });
        }

        // 关闭编辑弹窗
        // AI补全单词信息
        function aiCompleteWord() {
            const word = document.getElementById('editEnglish').value.trim();
            const category = document.getElementById('editCategory').value;
            
            if (!word) {
                showToast('请先输入英文单词', 'error');
                return;
            }
            
            const btn = event.target;
            const originalText = btn.textContent;
            btn.textContent = '生成中...';
            btn.disabled = true;
            
            fetch('/api/ai-complete-word', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    word: word,
                    category: category
                })
            })
            .then(response => response.json())
            .then(data => {
                btn.textContent = originalText;
                btn.disabled = false;
                
                if (data.success) {
                    // 填充音标和释义
                    if (data.british_phonetic) {
                        document.getElementById('editBritish').value = data.british_phonetic;
                    }
                    if (data.american_phonetic) {
                        document.getElementById('editAmerican').value = data.american_phonetic;
                    }
                    if (data.chinese_definition) {
                        document.getElementById('editDefinition').value = data.chinese_definition;
                    }
                    showToast('AI补全成功', 'success');
                } else {
                    showToast(data.message || 'AI补全失败', 'error');
                }
            })
            .catch(err => {
                console.error('AI补全失败:', err);
                btn.textContent = originalText;
                btn.disabled = false;
                showToast('AI补全失败，请稍后重试', 'error');
            });
        }
        
        function closeEditModal() {
            document.getElementById('editModal').classList.remove('show');
            editingWordId = null;
        }

        // 关闭删除弹窗
        function closeDeleteModal() {
            document.getElementById('deleteModal').classList.remove('show');
            deletingWordId = null;
        }

        // 加载分类选项
        function loadCategoryOptions() {
            return fetch('/api/admin/categories')
                .then(res => res.json())
                .then(categories => {
                    const select = document.getElementById('editCategory');
                    select.innerHTML = '';
                    categories.forEach(cat => {
                        const option = document.createElement('option');
                        option.value = cat.name;
                        option.textContent = cat.name;
                        select.appendChild(option);
                    });
                });
        }

        // Toast提示
        function showToast(message, type = 'success') {
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.className = 'toast ' + type;
            toast.classList.add('show');
            
            setTimeout(() => {
                toast.classList.remove('show');
            }, 3000);
        }

        // 点击弹窗外部关闭
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('click', function(e) {
                if (e.target === this) {
                    this.classList.remove('show');
                }
            });
        });

        // AI例句功能
        // 当前例句的单词和分类
        let currentExampleWord = '';
        let currentExampleCategory = '';
        
        // 渲染例句列表
        function renderExamples(examples) {
            const list = document.getElementById('exampleList');
            list.innerHTML = '';
            
            examples.forEach((example, index) => {
                const item = document.createElement('div');
                item.className = 'example-item';
                const englishText = example.english || '';
                item.innerHTML = `
                    <div class="example-english">
                        ${englishText}
                        <span class="example-speak" title="点击朗读">🔊</span>
                    </div>
                    ${example.chinese ? `<div class="example-chinese">${example.chinese}</div>` : ''}
                `;
                
                // 添加朗读事件
                const speakBtn = item.querySelector('.example-speak');
                if (speakBtn && englishText) {
                    speakBtn.addEventListener('click', function(e) {
                        e.stopPropagation();
                        speak(englishText, 'american', this);
                    });
                }
                
                list.appendChild(item);
            });
        }
        
        // 从缓存获取例句
        function getCachedExamples(word) {
            try {
                const cache = localStorage.getItem('ai_examples_cache');
                if (cache) {
                    const cacheData = JSON.parse(cache);
                    const cacheKey = word.toLowerCase();
                    if (cacheData[cacheKey]) {
                        // 缓存有效期30天
                        const now = Date.now();
                        if (now - cacheData[cacheKey].timestamp < 30 * 24 * 60 * 60 * 1000) {
                            return cacheData[cacheKey].examples;
                        }
                    }
                }
            } catch (e) {
                console.warn('读取缓存失败:', e);
            }
            return null;
        }
        
        // 保存例句到缓存
        function saveExamplesToCache(word, examples) {
            try {
                let cacheData = {};
                const cache = localStorage.getItem('ai_examples_cache');
                if (cache) {
                    cacheData = JSON.parse(cache);
                }
                const cacheKey = word.toLowerCase();
                cacheData[cacheKey] = {
                    examples: examples,
                    timestamp: Date.now()
                };
                localStorage.setItem('ai_examples_cache', JSON.stringify(cacheData));
            } catch (e) {
                console.warn('保存缓存失败:', e);
            }
        }
        
        // 清除单词的例句缓存
        function clearExampleCache(word) {
            try {
                const cache = localStorage.getItem('ai_examples_cache');
                if (cache) {
                    const cacheData = JSON.parse(cache);
                    const cacheKey = word.toLowerCase();
                    delete cacheData[cacheKey];
                    localStorage.setItem('ai_examples_cache', JSON.stringify(cacheData));
                }
            } catch (e) {
                console.warn('清除缓存失败:', e);
            }
        }
        
        // 调用API生成例句
        function fetchExamples(word, category) {
            return fetch('/api/ai-example', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    word: word,
                    category: category
                })
            })
            .then(response => response.json());
        }
        
        // 打开例句弹窗
        function openExampleModal(word, category) {
            const modal = document.getElementById('exampleModal');
            const title = document.getElementById('exampleModalTitle');
            const loading = document.getElementById('exampleLoading');
            const list = document.getElementById('exampleList');
            const error = document.getElementById('exampleError');
            const refreshBtn = document.getElementById('refreshExampleBtn');
            
            currentExampleWord = word;
            currentExampleCategory = category;
            
            title.textContent = `「${word}」AI例句`;
            loading.style.display = 'block';
            list.style.display = 'none';
            error.style.display = 'none';
            list.innerHTML = '';
            refreshBtn.style.display = 'none';
            
            modal.classList.add('show');
            
            // 先检查缓存
            const cachedExamples = getCachedExamples(word);
            if (cachedExamples && cachedExamples.length > 0) {
                // 有缓存，直接显示
                loading.style.display = 'none';
                renderExamples(cachedExamples);
                list.style.display = 'block';
                refreshBtn.style.display = 'inline-block';
                return;
            }
            
            // 没有缓存，调用API生成
            fetchExamples(word, category)
            .then(data => {
                loading.style.display = 'none';
                
                if (data.success && data.examples && data.examples.length > 0) {
                    // 保存到缓存
                    saveExamplesToCache(word, data.examples);
                    
                    // 显示例句
                    renderExamples(data.examples);
                    list.style.display = 'block';
                    refreshBtn.style.display = 'inline-block';
                } else {
                    // 显示错误
                    error.textContent = data.message || '生成例句失败';
                    error.style.display = 'block';
                }
            })
            .catch(err => {
                console.error('生成例句失败:', err);
                loading.style.display = 'none';
                error.textContent = '生成例句失败，请稍后重试';
                error.style.display = 'block';
            });
        }
        
        // 刷新例句（重新生成）
        function refreshExample() {
            const loading = document.getElementById('exampleLoading');
            const list = document.getElementById('exampleList');
            const error = document.getElementById('exampleError');
            const refreshBtn = document.getElementById('refreshExampleBtn');
            
            if (!currentExampleWord) return;
            
            // 清除缓存
            clearExampleCache(currentExampleWord);
            
            loading.style.display = 'block';
            list.style.display = 'none';
            error.style.display = 'none';
            list.innerHTML = '';
            refreshBtn.style.display = 'none';
            
            // 重新生成
            fetchExamples(currentExampleWord, currentExampleCategory)
            .then(data => {
                loading.style.display = 'none';
                
                if (data.success && data.examples && data.examples.length > 0) {
                    // 保存到缓存
                    saveExamplesToCache(currentExampleWord, data.examples);
                    
                    // 显示例句
                    renderExamples(data.examples);
                    list.style.display = 'block';
                    refreshBtn.style.display = 'inline-block';
                } else {
                    // 显示错误
                    error.textContent = data.message || '生成例句失败';
                    error.style.display = 'block';
                }
            })
            .catch(err => {
                console.error('生成例句失败:', err);
                loading.style.display = 'none';
                error.textContent = '生成例句失败，请稍后重试';
                error.style.display = 'block';
            });
        }
        
        function closeExampleModal() {
            document.getElementById('exampleModal').classList.remove('show');
        }
        
        // 页面加载完成后
        document.addEventListener('DOMContentLoaded', function() {
            // 给AI例句按钮添加点击事件
            document.querySelectorAll('.ai-example-btn').forEach(btn => {
                btn.addEventListener('click', function() {
                    const word = this.dataset.word;
                    const category = this.dataset.category;
                    openExampleModal(word, category);
                });
            });
        });

