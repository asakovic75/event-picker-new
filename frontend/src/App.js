import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import './App.css';
import { useTranslation } from 'react-i18next';

const API_URL = 'http://localhost:8000/api';
const AUTH_URL = `${API_URL}/auth`;
const USER_URL = `${API_URL}/profile`;
const FAV_URL = `${API_URL}/favorites`;
const CHAT_URL = `${API_URL}/chat`;

const categoryMap = {
  'Концерты': '/concerts.jpg',
  'Театр': '/theater.jpg',
  'Спектакли': '/theater.jpg',
  'Спорт': '/sport.jpg',
  'Фестивали': '/festivals.jpg',
  'Цирк': '/circus.jpg',
  'Детская афиша': '/children.jpg',
  'Дети': '/children.jpg',
  'Кино': '/cinema.jpg',
  'Выставки': '/exhibition.jpg',
  'Обучение': '/education.jpg',
  'Квесты': '/quest.jpg',
  'Событие': '/default.jpg',
  'События': '/default.jpg'
};

const defaultImg = '/default.jpg';

const formatDate = (dateStr) => {
  if (!dateStr) return 'Дата уточняется';
  try {
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return dateStr;
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = date.getFullYear();
    return `${day}.${month}.${year}`;
  } catch {
    return dateStr;
  }
};

const EventCard = ({ ev, onDetail, onFav, isFavorite = false }) => {
  let posterUrl = ev.poster_url || ev.постер || ev.poster;
  if (posterUrl && posterUrl.length > 5) {
    if (posterUrl.startsWith('/')) {
      posterUrl = `https://www.ticketpro.by${posterUrl}`;
    }
  } else {
    posterUrl = categoryMap[ev.category || ev.раздел] || defaultImg;
  }

  const title = ev.title || ev.название || 'Событие';
  const venue = ev.venue || ev.место || 'Место не указано';
  const date = formatDate(ev.date_start || ev.дата_начала);
  const price = ev.price_min || ev.цена_мин || 0;
  const priceText = price === 0 ? 'БЕСПЛАТНО 🎉' : `${price} руб.`;
  const category = ev.category || ev.раздел || 'Событие';
  const age = ev.age_restriction || ev.возраст || '';

  return (
    <div className="event-card">
      <div className="card-img-container">
        <img src={posterUrl} alt="" />
        <span className="badge category-white-pill">{category}</span>
        <button className="heart-btn" onClick={() => onFav(ev)}>
          {isFavorite ? '❤️' : '🤍'}
        </button>
      </div>
      <div className="card-content">
        <h3 className="card-title">{title}</h3>
        <p className="card-meta">📍 {venue}</p>
        <p className="card-meta">📅 {date}</p>
        {age && <p className="card-meta">🔞 {age}</p>}
        <div className="card-footer">
          <span className="card-price">{priceText}</span>
          <button className="btn-detail-pill" onClick={() => onDetail(ev)}>Подробнее ›</button>
        </div>
      </div>
    </div>
  );
};

function App() {
  const { t, i18n } = useTranslation();
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [userData, setUserData] = useState({ id: '', username: '', name: '', email: '', city: 'Гродно', interests: [] });
  const [activeTab, setActiveTab] = useState('search');
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [favorites, setFavorites] = useState([]);
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Привет! Я твой помощник по событиям. Что ищем сегодня в Гродно?', isStart: true }
  ]);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const scrollRef = useRef();
  const [isEditing, setIsEditing] = useState(false);
  const [editForm, setEditForm] = useState({ name: '', city: '', interests: [] });

  const changeLanguage = (lang) => {
    i18n.changeLanguage(lang);
    localStorage.setItem('language', lang);
  };

  const loadFavorites = useCallback(async () => {
    try {
      if (!token) return;
      const res = await axios.get(`${FAV_URL}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      let favs = [];
      if (res.data && res.data.favorites) {
        favs = res.data.favorites;
      } else if (Array.isArray(res.data)) {
        favs = res.data;
      } else if (res.data.data && Array.isArray(res.data.data)) {
        favs = res.data.data;
      }
      setFavorites(favs);
    } catch (e) { 
      console.error("Ошибка избранного", e); 
      setFavorites([]);
    }
  }, [token]);

  const loadUserData = async (tkn) => {
    try {
      const res = await axios.get(`${USER_URL}`, {
        headers: { 'Authorization': `Bearer ${tkn}` }
      });
      const userDataResponse = {
        id: res.data.id || res.data.user_id || '',
        username: res.data.username || '',
        name: res.data.name || res.data.username || '',
        email: res.data.username || '',
        city: res.data.city || 'Гродно',
        interests: res.data.interests || []
      };
      setUserData(userDataResponse);
      setEditForm({ 
        name: userDataResponse.name, 
        city: userDataResponse.city, 
        interests: userDataResponse.interests || [] 
      });
    } catch (e) { 
      console.error("Ошибка профиля:", e);
    }
  };

  useEffect(() => {
    if (token) {
      loadUserData(token);
    }
  }, [token]);

  useEffect(() => {
    if (userData.id) {
      loadFavorites();
    }
  }, [userData.id, loadFavorites]);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleLogin = async (email, password) => {
    try {
      const res = await axios.post(`${AUTH_URL}/login`, { 
        username: email, 
        password: password 
      });
      if (res.data && res.data.access_token) {
        localStorage.setItem('token', res.data.access_token);
        setToken(res.data.access_token);
        setActiveTab('search');
      } else {
        alert('Ошибка входа: токен не получен');
      }
    } catch (e) { 
      console.error("Ошибка входа:", e);
      alert(e.response?.data?.detail || "Ошибка входа"); 
    }
  };

  const handleRegister = async (email, password, name, city, interests) => {
    try {
      await axios.post(`${AUTH_URL}/register`, { 
        username: email,
        password: password,
        name: name,
        city: city,
        interests: interests
      });
      await handleLogin(email, password);
    } catch (e) { 
      console.error("Ошибка регистрации:", e);
      alert(e.response?.data?.detail || "Ошибка регистрации"); 
    }
  };

  const sendMessage = async (textOverride) => {
    const query = textOverride || inputText;
    if (!query.trim()) return;
    if (!textOverride) {
      setMessages(prev => [...prev, { role: 'user', content: query }]);
      setInputText('');
    }
    setIsLoading(true);
    try {
      const res = await axios.post(CHAT_URL, 
        { query: query, city: userData.city },
        { headers: { 'Authorization': `Bearer ${token}` } }
      );
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: res.data.response,
        events: res.data.events || [],
        query: query
      }]);
    } catch (e) {
      console.error("Ошибка чата:", e);
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: 'Извините, произошла ошибка. Попробуйте позже.' 
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const toggleFavorite = async (ev) => {
    try {
      if (!userData.id) {
        alert("Ошибка: ID пользователя не найден.");
        return;
      }
      
      const eventId = ev.id;
      const isFav = favorites.some(f => (f.event_id || f.id) === eventId);
      
      if (isFav) {
        await axios.delete(`${FAV_URL}/${eventId}`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        await loadFavorites();
        alert("🗑 Удалено из избранного");
      } else {
        await axios.post(
          `${FAV_URL}?event_id=${eventId}`,
          {},
          { 
            headers: { 
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json' 
            } 
          }
        );
        await loadFavorites();
        alert("✅ Добавлено в избранное!");
      }
    } catch(e) { 
      console.error("Ошибка:", e);
      alert("Ошибка при изменении избранного");
    }
  };

  const removeFromFav = async (eventId) => {
    try {
      if (!userData.id) {
        alert("Ошибка: ID пользователя не найден.");
        return;
      }
      await axios.delete(`${FAV_URL}/${eventId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      await loadFavorites();
    } catch(e) { 
      console.error("Ошибка при удалении:", e);
      alert("Ошибка при удалении из избранного"); 
    }
  };

  const handleEditProfile = async () => {
    try {
      if (!userData.id) {
        alert("Ошибка: ID пользователя не найден.");
        return;
      }
      await axios.put(
        `${USER_URL}`,
        editForm,
        { headers: { 'Authorization': `Bearer ${token}` } }
      );
      setUserData({ ...userData, ...editForm });
      setIsEditing(false);
      alert("✅ Профиль обновлен!");
    } catch(e) { 
      console.error("Ошибка при обновлении:", e);
      alert("Ошибка при обновлении профиля"); 
    }
  };

  if (!token) return <AuthScreen onLogin={handleLogin} onRegister={handleRegister} />;

  return (
    <div className="app-container">
      {selectedEvent && <DetailsView event={selectedEvent} onBack={() => setSelectedEvent(null)} />}

      <div className="app-header">
        <img src="/logo.png" className="header-logo-small" alt="Logo" />
        <div style={{textAlign:'left', marginLeft:'5px', flex:1}}>
          <h2 style={{fontSize:'19px', fontWeight:800}}>
            {activeTab === 'search' ? t('app.title') : t('app.profile')}
          </h2>
          <p style={{fontSize:'12px', color:'#888', fontWeight: 500}}>
            {activeTab === 'search' ? `${userData.city} • Афиша событий` : `${userData.city} • Личный кабинет`}
          </p>
        </div>
        <div style={{display:'flex', gap:'4px'}}>
          <button 
            onClick={() => changeLanguage('ru')} 
            style={{background: i18n.language === 'ru' ? '#5d83f1' : 'transparent', color: i18n.language === 'ru' ? 'white' : '#888', border: '1px solid #ddd', borderRadius: '8px', padding: '4px 8px', cursor: 'pointer', fontSize: '14px'}}
          >🇷🇺</button>
          <button 
            onClick={() => changeLanguage('be')} 
            style={{background: i18n.language === 'be' ? '#5d83f1' : 'transparent', color: i18n.language === 'be' ? 'white' : '#888', border: '1px solid #ddd', borderRadius: '8px', padding: '4px 8px', cursor: 'pointer', fontSize: '14px'}}
          >🇧🇾</button>
          <button 
            onClick={() => changeLanguage('en')} 
            style={{background: i18n.language === 'en' ? '#5d83f1' : 'transparent', color: i18n.language === 'en' ? 'white' : '#888', border: '1px solid #ddd', borderRadius: '8px', padding: '4px 8px', cursor: 'pointer', fontSize: '14px'}}
          >🇬🇧</button>
        </div>
      </div>

      <div className="main-content">
        {activeTab === 'search' ? (
          <>
            <div className="messages-area">
              {messages.map((m, i) => (
                <div key={i} className={`msg-wrapper ${m.role}`}>
                  <div className="msg-bubble">
                    {m.content}
                    {m.isStart && (
                        <div className="chips-list-vertical" style={{display:'flex', flexDirection:'column', gap:'10px', marginTop:'15px'}}>
                            <button className="chip-btn-wide" onClick={() => sendMessage(t('chips.today'))}>📅 {t('chips.today')}</button>
                            <button className="chip-btn-wide" onClick={() => sendMessage(t('chips.free'))}>🎁 {t('chips.free')}</button>
                            <button className="chip-btn-wide" onClick={() => sendMessage(t('chips.kids'))}>👨‍👩‍👧 {t('chips.kids')}</button>
                            <button className="chip-btn-wide" onClick={() => sendMessage(t('chips.weekend'))}>🌟 {t('chips.weekend')}</button>
                        </div>
                    )}
                    {m.events && m.events.length > 0 && (
                      <div className="events-grid">
                        {m.events.map(ev => (
                          <EventCard 
                            key={ev.id} 
                            ev={ev} 
                            onDetail={setSelectedEvent} 
                            onFav={toggleFavorite}
                            isFavorite={favorites.some(f => (f.event_id || f.id) === ev.id)}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {isLoading && (
                <div className="msg-wrapper assistant">
                  <div className="msg-bubble" style={{background:'#f3f4f6', fontStyle:'italic'}}>{t('loading')}</div>
                </div>
              )}
              <div ref={scrollRef} />
            </div>
            <div className="input-section">
              <div className="pill-input">
                  <input placeholder={t('app.search_placeholder')} value={inputText} onChange={e=>setInputText(e.target.value)} onKeyPress={e=>e.key==='Enter' && sendMessage()}/>
                  <button className="btn-send-icon" onClick={()=>sendMessage()}>➤</button>
              </div>
            </div>
          </>
        ) : (
          <ProfileView 
            userData={userData} 
            favorites={favorites} 
            onLogout={()=>{localStorage.clear(); setToken(null);}}
            onRemoveFav={removeFromFav}
            onEdit={handleEditProfile}
            onDetail={setSelectedEvent}
            isEditing={isEditing}
            setIsEditing={setIsEditing}
            editForm={editForm}
            setEditForm={setEditForm}
          />
        )}
      </div>

      <nav className="bottom-nav">
          <button className={`nav-item ${activeTab==='search'?'active':''}`} onClick={()=>setActiveTab('search')}>
              <span className="nav-icon">💬</span><span className="nav-text">{t('app.search')}</span>
          </button>
          <button className={`nav-item ${activeTab==='profile'?'active':''}`} onClick={()=>setActiveTab('profile')}>
              <span className="nav-icon">👤</span><span className="nav-text">{t('app.profile')}</span>
          </button>
      </nav>
    </div>
  );
}

function ProfileView({ 
  userData, 
  favorites = [], 
  onLogout, 
  onRemoveFav, 
  onDetail,
  isEditing,
  setIsEditing,
  editForm,
  setEditForm,
  onEdit
}) {
  const { t } = useTranslation();
  const categories = ["Концерты", "Театр", "Спектакли", "Спорт", "Фестивали", "Цирк", "Детская афиша", "Кино", "Выставки", "Обучение", "Квесты"];
  const cities = ["Гродно", "Минск", "Брест", "Могилев", "Витебск", "Гомель"];
  
  const toggleInterest = (cat) => {
    setEditForm(prev => ({
      ...prev, 
      interests: prev.interests.includes(cat) 
        ? prev.interests.filter(i => i !== cat) 
        : [...prev.interests, cat]
    }));
  };

  const getPosterUrl = (eventData) => {
    let posterUrl = eventData?.poster_url || eventData?.постер || eventData?.poster;
    if (posterUrl && posterUrl.length > 5) {
      if (posterUrl.startsWith('/')) {
        posterUrl = `https://www.ticketpro.by${posterUrl}`;
      }
    } else {
      posterUrl = categoryMap[eventData?.category || eventData?.раздел] || defaultImg;
    }
    return posterUrl;
  };

  const formatDateDisplay = (dateStr) => {
    if (!dateStr) return 'Дата уточняется';
    try {
      const date = new Date(dateStr);
      if (isNaN(date.getTime())) return dateStr;
      const day = String(date.getDate()).padStart(2, '0');
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const year = date.getFullYear();
      return `${day}.${month}.${year}`;
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="profile-scroll-area">
      <div className="profile-section-card">
        <div className="profile-header-row">
          <h3 className="bold-title">{t('profile.my_data')}</h3>
          {!isEditing ? (
            <button className="edit-link-blue" onClick={() => setIsEditing(true)}>✎ {t('profile.edit')}</button>
          ) : (
            <div style={{display: 'flex', gap: '8px'}}>
              <button className="edit-link-blue" onClick={onEdit}>💾 {t('profile.save')}</button>
              <button className="edit-link-blue" onClick={() => {
                setIsEditing(false);
                setEditForm({ name: userData.name, city: userData.city, interests: userData.interests || [] });
              }}>✕ {t('profile.cancel')}</button>
            </div>
          )}
        </div>
        
        <p className="label-normal">{t('profile.username')}</p>
        {isEditing ? (
          <input 
            className="auth-input" 
            value={editForm.name} 
            onChange={e => setEditForm({...editForm, name: e.target.value})}
          />
        ) : (
          <p className="value-normal">{userData?.name || ''}</p>
        )}
        
        <p className="label-normal">{t('profile.email')}</p>
        {isEditing ? (
          <input 
            className="auth-input" 
            value={userData.username || userData.email || ''} 
            disabled
            style={{background: '#f0f0f0', cursor: 'not-allowed'}}
          />
        ) : (
          <p className="value-normal">{userData.username || userData.email || ''}</p>
        )}
        
        <p className="label-normal">{t('profile.city')}</p>
        {isEditing ? (
          <select 
            className="auth-input" 
            value={editForm.city} 
            onChange={e => setEditForm({...editForm, city: e.target.value})}
          >
            {cities.map(city => (
              <option key={city} value={city}>{city}</option>
            ))}
          </select>
        ) : (
          <p className="value-normal">{userData?.city || 'Гродно'}</p>
        )}
        
        <p className="label-normal">{t('profile.interests')}</p>
        {isEditing ? (
          <div className="interests-list">
            {categories.map(cat => (
              <button 
                key={cat} 
                type="button" 
                className={`interest-pill ${editForm.interests.includes(cat) ? 'active' : ''}`}
                onClick={() => toggleInterest(cat)}
              >
                {cat}
              </button>
            ))}
          </div>
        ) : (
          <div className="interests-container">
            {(userData?.interests || []).map(i => (
              <span key={i} className="interest-pill-gray">{i}</span>
            ))}
          </div>
        )}
      </div>

      <h3 className="bold-title" style={{marginLeft: '5px'}}>{t('profile.favorites')}</h3>
      {favorites.length > 0 ? (
        favorites.map(fav => {
          const eventData = fav.events || fav;
          const posterUrl = getPosterUrl(eventData);
          const title = eventData?.title || eventData?.название || 'Событие';
          const venue = eventData?.venue || eventData?.место || 'Место не указано';
          const date = formatDateDisplay(eventData?.date_start || eventData?.дата_начала);
          const price = eventData?.price_min || eventData?.цена_мин || 0;
          const priceText = price === 0 ? 'БЕСПЛАТНО 🎉' : `${price} руб.`;
          const age = eventData?.age_restriction || eventData?.возраст || '';

          return (
            <div key={fav.id || fav.event_id} className="fav-horizontal-card" onClick={() => onDetail(eventData)}>
              <img 
                src={posterUrl} 
                className="fav-img-thumb" 
                alt="" 
                onError={(e) => { e.target.src = defaultImg; }} 
              />
              <div className="fav-info-box">
                <h4 className="fav-title">{title}</h4>
                <p className="fav-place">📍 {venue}</p>
                <p className="fav-place">📅 {date}</p>
                {age && <p className="fav-place">🔞 {age}</p>}
                <p className="fav-place" style={{fontWeight: 'bold', color: '#5d83f1'}}>💰 {priceText}</p>
              </div>
              <button className="del-btn-icon" onClick={(e) => { e.stopPropagation(); onRemoveFav(fav.event_id || fav.id); }}>🗑</button>
            </div>
          );
        })
      ) : (
        <p className="empty-fav">{t('profile.no_favorites')}</p>
      )}

      <button className="logout-pill-btn-bold" onClick={onLogout}>
        <span className="logout-icon">→</span> 
        {t('profile.logout')}
      </button>
      
      <div className="bottom-spacer"></div>
    </div>
  );
}

function AuthScreen({ onLogin, onRegister }) {
  const { t } = useTranslation();
  const [isLogin, setIsLogin] = useState(true);
  const [form, setForm] = useState({ email: '', password: '', name: '', city: 'Гродно', interests: [] });
  const categories = ["Концерты", "Театр", "Спектакли", "Спорт", "Фестивали", "Цирк", "Детская афиша", "Кино", "Выставки", "Обучение", "Квесты"];
  const cities = ["Гродно", "Минск", "Брест", "Могилев", "Витебск", "Гомель"];
  
  const toggleInterest = (cat) => {
    setForm(prev => ({
      ...prev, interests: prev.interests.includes(cat) ? prev.interests.filter(i=>i!==cat) : [...prev.interests, cat]
    }));
  };
  
  return (
    <div className="auth-overlay">
      <div className="auth-card">
        <img src="/logo.png" className="auth-logo" alt="Logo" />
        <h1 style={{fontSize:24}}>{t('app.title')}</h1>
        <p className="auth-subtitle">{t('auth.welcome')}</p>
        <div className="auth-tabs">
          <button type="button" className={`auth-tab ${isLogin ? 'active' : ''}`} onClick={()=>setIsLogin(true)}>{t('auth.login')}</button>
          <button type="button" className={`auth-tab ${!isLogin ? 'active' : ''}`} onClick={()=>setIsLogin(false)}>{t('auth.register')}</button>
        </div>
        <div className="input-group">
          <label className="input-label">{t('auth.email')}</label>
          <input className="auth-input" placeholder="you@mail.com" value={form.email} onChange={e=>setForm({...form, email:e.target.value})} />
        </div>
        <div className="input-group">
          <label className="input-label">{t('auth.password')}</label>
          <input className="auth-input" type="password" placeholder="••••••••" value={form.password} onChange={e=>setForm({...form, password:e.target.value})} />
        </div>
        {!isLogin && (
          <>
            <div className="input-group">
              <label className="input-label">{t('auth.name')}</label>
              <input className="auth-input" placeholder="Анна" value={form.name} onChange={e=>setForm({...form, name:e.target.value})} />
            </div>
            <div className="input-group">
              <label className="input-label">{t('auth.city')}</label>
              <select className="auth-input" value={form.city} onChange={e=>setForm({...form, city:e.target.value})}>
                {cities.map(city => (
                  <option key={city} value={city}>{city}</option>
                ))}
              </select>
            </div>
            <div className="input-group">
              <label className="input-label">{t('profile.interests')}</label>
              <div className="interests-list">
                {categories.map(cat => (
                  <button key={cat} type="button" className={`interest-pill ${form.interests.includes(cat)?'active':''}`} onClick={()=>toggleInterest(cat)}>{cat}</button>
                ))}
              </div>
            </div>
          </>
        )}
        <button className="auth-button-main" onClick={()=> isLogin ? onLogin(form.email, form.password) : onRegister(form.email, form.password, form.name, form.city, form.interests)}>
          {isLogin ? t('auth.login') : t('auth.register')}
        </button>
      </div>
    </div>
  );
}

function DetailsView({ event, onBack }) {
  let posterUrl = event.poster_url || event.постер || event.poster;
  if (posterUrl && posterUrl.length > 5) {
      if (posterUrl.startsWith('/')) posterUrl = `https://www.ticketpro.by${posterUrl}`;
  } else {
      posterUrl = categoryMap[event.category || event.раздел] || defaultImg;
  }

  const title = event.title || event.название || 'Событие';
  const date = event.date_start || event.дата_начала || 'Дата уточняется';
  const venue = event.venue || event.место || 'Место не указано';
  const price = event.price_min || event.цена_мин || 0;
  const priceText = price === 0 ? 'БЕСПЛАТНО 🎉' : `${price} руб.`;
  const category = event.category || event.раздел || 'Событие';
  const description = event.description || event.описание || 'Описание отсутствует';
  const ticketUrl = event.ticket_url || event.ссылка || '#';
  const age = event.age_restriction || event.возраст || '';

  const formatDateDisplay = (dateStr) => {
    if (!dateStr) return 'Дата уточняется';
    try {
      const date = new Date(dateStr);
      if (isNaN(date.getTime())) return dateStr;
      const day = String(date.getDate()).padStart(2, '0');
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const year = date.getFullYear();
      return `${day}.${month}.${year}`;
    } catch {
      return dateStr;
    }
  };

  const lat = parseFloat(event.latitude);
  const lon = parseFloat(event.longitude);
  const zoom = 0.003; 
  const mapEmbedUrl = (lat && lon) 
    ? `https://www.openstreetmap.org/export/embed.html?bbox=${lon-zoom}%2C${lat-zoom}%2C${lon+zoom}%2C${lat+zoom}&layer=mapnik&marker=${lat}%2C${lon}`
    : null;

  return (
    <div className="details-overlay">
      <div className="details-container-inner">
        <div className="details-header">
          <button className="details-back-icon" onClick={onBack}>‹</button>
          <span className="details-header-title">Детали события</span>
        </div>

        <div className="details-scroll-content">
          <div className="details-category-pill">{category}</div>
          
          <h1 className="details-main-title">{title}</h1>

          <div className="details-poster-box">
            <img 
              src={posterUrl} 
              alt={title} 
              onError={(e) => { e.target.src = defaultImg; }}
            />
          </div>

          <div className="details-info-grid" style={{gridTemplateColumns: '1fr', gap: '8px'}}>
            <div className="info-block-item">
              <div className="info-icon-circle">📅</div>
              <div className="info-text-box">
                <span className="info-small-label">Дата</span>
                <span className="info-main-value">{formatDateDisplay(date)}</span>
              </div>
            </div>
            <div className="info-block-item">
              <div className="info-icon-circle">💰</div>
              <div className="info-text-box">
                <span className="info-small-label">Цена</span>
                <span className="info-main-value">{priceText}</span>
              </div>
            </div>
            <div className="info-block-item">
              <div className="info-icon-circle">📍</div>
              <div className="info-text-box">
                <span className="info-small-label">Место</span>
                <span className="info-main-value">{venue}</span>
              </div>
            </div>
            {age && (
              <div className="info-block-item">
                <div className="info-icon-circle">🔞</div>
                <div className="info-text-box">
                  <span className="info-small-label">Возраст</span>
                  <span className="info-main-value">{age}</span>
                </div>
              </div>
            )}
          </div>

          {mapEmbedUrl && (
            <div className="map-section-wrapper">
              <h3 className="details-sub-title">📍 Место на карте</h3>
              <iframe 
                title="map" 
                className="details-map-frame" 
                src={mapEmbedUrl}
                style={{width: '100%', height: '250px', borderRadius: '16px', border: '1px solid #eee'}}
              ></iframe>
            </div>
          )}

          <h3 className="details-sub-title">Описание</h3>
          <p className="details-text-desc">{description}</p>

          <div style={{height: '100px'}}></div>
        </div>

        <div className="details-bottom-actions">
          <a href={ticketUrl} target="_blank" rel="noreferrer" className="details-buy-btn-full">
            Купить билет
          </a>
        </div>
      </div>
    </div>
  );
}

export default App;