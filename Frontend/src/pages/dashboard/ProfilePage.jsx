import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { absoluteMediaUrl, deleteBusinessMedia, getBusinessLocation, getBusinessMedia, getBusinessProfile, saveBusinessLocation, saveBusinessProfile, uploadBusinessMedia } from "../../services/api";
import DashboardShell from "./DashboardShell";
import BusinessLocationPicker from "../../components/BusinessLocationPicker";
import "./dashboard.css";

const blank={display_name:"",description:"",category:"restaurant",phone_number:"",website:"",email:"",full_address:"",city:"Ottawa",postal_code:"",hours_json:"",amenities_json:"",logo_url:"",cover_photo_url:"",is_published:false};

const BUSINESS_CATEGORIES = [
  "restaurant", "cafe", "bakery", "bar", "food truck",
  "plumber", "electrician", "HVAC", "cleaner", "handyman",
  "dentist", "clinic", "pharmacy", "salon", "barber",
  "lawyer", "accountant", "real estate", "tutor", "mechanic",
  "pet services", "photographer", "fitness", "retail", "other",
];
const DAYS=[
 {key:"monday",label:"Monday"},{key:"tuesday",label:"Tuesday"},{key:"wednesday",label:"Wednesday"},
 {key:"thursday",label:"Thursday"},{key:"friday",label:"Friday"},{key:"saturday",label:"Saturday"},{key:"sunday",label:"Sunday"},
];
const DEFAULT_HOURS={closed:false,open:"09:00",close:"17:00"};

function normalizeHours(raw){
 const defaults=Object.fromEntries(DAYS.map(day=>[day.key,{...DEFAULT_HOURS}]));
 if(!raw) return defaults;
 try{
  const parsed=typeof raw==="string"?JSON.parse(raw):raw;
  for(const {key} of DAYS){
   const value=parsed?.[key];
   if(typeof value==="string"){
    if(value.toLowerCase()==="closed") defaults[key]={...DEFAULT_HOURS,closed:true};
    else {
     const [open,close]=value.split("-");
     defaults[key]={closed:false,open:open||"09:00",close:close||"17:00"};
    }
   } else if(value&&typeof value==="object"){
    defaults[key]={
     closed:Boolean(value.closed),
     open:value.open||value.opens||"09:00",
     close:value.close||value.closes||"17:00",
    };
   }
  }
 }catch{/* Keep safe defaults if legacy JSON is malformed. */}
 return defaults;
}
const AMENITY_GROUPS=[
 {title:"Service",icon:"🍽️",key:"services",options:[["dine_in","Dine-in"],["takeout","Takeout"],["delivery","Delivery"],["catering","Catering"],["reservations","Reservations"]]},
 {title:"Parking",icon:"🅿️",key:"parking",options:[["free_parking","Free parking"],["paid_parking","Paid parking"],["street_parking","Street parking"]]},
 {title:"Seating",icon:"🌤️",key:"seating",options:[["indoor_seating","Indoor seating"],["patio","Patio / outdoor seating"]]},
 {title:"Accessibility",icon:"♿",key:"accessibility",options:[["wheelchair_entrance","Wheelchair-accessible entrance"],["wheelchair_seating","Wheelchair-accessible seating"],["wheelchair_washroom","Wheelchair-accessible washroom"]]},
 {title:"Family",icon:"👨‍👩‍👧",key:"family",options:[["kids_menu","Kids menu"],["high_chairs","High chairs"],["family_friendly","Family-friendly"]]},
 {title:"Amenities",icon:"📶",key:"amenities",options:[["wifi","Wi-Fi"],["washroom","Washroom"],["charging_outlets","Charging outlets"]]},
 {title:"Payments",icon:"💳",key:"payments",options:[["credit_card","Credit card"],["debit","Debit"],["cash","Cash"],["contactless","Contactless payment"]]},
];
const DEFAULT_AMENITIES={
 services:[],parking:[],seating:[],accessibility:[],family:[],amenities:[],payments:[],
 halal_status:"unknown", alcohol_status:"unknown", dietary:[],
 halal_evidence_url:"", halal_certificate_note:"",
};
function normalizeAmenities(raw){
 const base={...DEFAULT_AMENITIES};
 for(const key of ["services","parking","seating","accessibility","family","amenities","payments","dietary"]) base[key]=[];
 if(!raw) return base;
 try{
  const parsed=typeof raw==="string"?JSON.parse(raw):raw;
  if(!parsed||typeof parsed!=="object") return base;
  for(const key of Object.keys(base)){
   if(Array.isArray(base[key])) base[key]=Array.isArray(parsed[key])?[...parsed[key]]:[];
   else if(typeof parsed[key]==="string") base[key]=parsed[key];
  }
 }catch{/* Keep defaults for legacy or malformed data. */}
 return base;
}
function amenitiesToJson(value){return JSON.stringify(value);}

function hoursToJson(hours){
 const payload={};
 for(const {key} of DAYS){
  const value=hours[key]||DEFAULT_HOURS;
  payload[key]=value.closed?{closed:true}:{closed:false,open:value.open||"09:00",close:value.close||"17:00"};
 }
 return JSON.stringify(payload);
}

export default function ProfilePage(){
 const {token,user}=useAuth();
 const [form,setForm]=useState({...blank,display_name:user.business_name||user.name});
 const [businessHours,setBusinessHours]=useState(()=>normalizeHours(""));
 const [amenities,setAmenities]=useState(()=>normalizeAmenities(""));
 const [businessLocation,setBusinessLocation]=useState(null);
 const [media,setMedia]=useState([]); const [message,setMessage]=useState(""); const [error,setError]=useState(""); const [uploading,setUploading]=useState("");
 async function load(){try{const [profile,items,location]=await Promise.all([getBusinessProfile(token),getBusinessMedia(token),getBusinessLocation(token)]);if(profile){setForm({...blank,...profile});setBusinessHours(normalizeHours(profile.hours_json));setAmenities(normalizeAmenities(profile.amenities_json));}setMedia(items||[]);if(location&&Number.isFinite(Number(location.latitude))&&Number.isFinite(Number(location.longitude))){setBusinessLocation({latitude:Number(location.latitude),longitude:Number(location.longitude),source:"saved"});}}catch(e){setError(e.message)}}
 useEffect(()=>{load()},[token]);
 const gallery=useMemo(()=>media.filter(x=>x.media_type==="gallery"),[media]);
 const set=(key)=>(e)=>setForm(v=>({...v,[key]:e.target.type==="checkbox"?e.target.checked:e.target.value}));
 const updateDay=(day,patch)=>setBusinessHours(current=>({...current,[day]:{...current[day],...patch}}));
 const copyDay=(source,targets)=>setBusinessHours(current=>{const next={...current};for(const day of targets)next[day]={...current[source]};return next;});
 const toggleAmenity=(group,key)=>setAmenities(current=>{const list=current[group]||[];return {...current,[group]:list.includes(key)?list.filter(item=>item!==key):[...list,key]};});
 const setAmenity=(key,value)=>setAmenities(current=>({...current,[key]:value}));
 async function submit(e){e.preventDefault();try{setError("");setMessage("");if(form.is_published&&!businessLocation){setError("Confirm your exact map pin before publishing. This keeps near-me results and directions accurate.");return;}const payload={...form,hours_json:hoursToJson(businessHours),amenities_json:amenitiesToJson(amenities)};const data=await saveBusinessProfile(token,payload);if(businessLocation){const savedLocation=await saveBusinessLocation(token,{latitude:Number(businessLocation.latitude),longitude:Number(businessLocation.longitude)});setBusinessLocation({...businessLocation,latitude:Number(savedLocation.latitude),longitude:Number(savedLocation.longitude),source:"saved"});}setForm({...blank,...data});setBusinessHours(normalizeHours(data.hours_json));setAmenities(normalizeAmenities(data.amenities_json));setMessage(businessLocation?"Your business profile and exact map pin were saved.":"Your business profile was saved. Add an exact map pin for reliable near-me results.")}catch(err){setError(err.message)}}
 async function upload(type,file){if(!file)return;try{setUploading(type);setError("");await uploadBusinessMedia(token,type,file);await load();setMessage(`${type[0].toUpperCase()+type.slice(1)} photo uploaded.`)}catch(e){setError(e.message)}finally{setUploading("")}}
 async function remove(id){try{await deleteBusinessMedia(token,id);await load();setMessage("Photo removed.")}catch(e){setError(e.message)}}
 const logo=media.find(x=>x.media_type==="logo"); const cover=media.find(x=>x.media_type==="cover");
 return <DashboardShell><div className="dashboard-heading"><div><p className="dashboard-eyebrow">BUSINESS PROFILE</p><h1>Manage your information</h1><p>Customers will see this information on your public profile.</p></div></div>
 <form className="dashboard-form" onSubmit={submit}>
 <section className="dashboard-panel form-section"><h2>Photos</h2><p className="field-help">Upload JPG, PNG, or WEBP images up to 8 MB. Gallery supports up to 12 photos.</p><div className="media-manager-grid">
 <MediaSlot title="Logo" item={logo} busy={uploading==="logo"} onUpload={file=>upload("logo",file)} onDelete={()=>remove(logo.id)}/><MediaSlot title="Cover photo" item={cover} wide busy={uploading==="cover"} onUpload={file=>upload("cover",file)} onDelete={()=>remove(cover.id)}/></div>
 <div className="gallery-manager"><div className="gallery-manager-heading"><h3>Gallery</h3><label className="dashboard-primary media-upload-button">{uploading==="gallery"?"Uploading...":"Add photos"}<input type="file" accept="image/jpeg,image/png,image/webp" multiple disabled={!!uploading} onChange={async e=>{for(const file of Array.from(e.target.files||[])) await upload("gallery",file);e.target.value=""}}/></label></div><div className="gallery-manager-grid">{gallery.map(item=><div className="gallery-manager-card" key={item.id}><img src={absoluteMediaUrl(item.file_url)} alt="Business gallery"/><button type="button" onClick={()=>remove(item.id)}>Remove</button></div>)}{gallery.length===0&&<p className="field-help">No gallery photos yet.</p>}</div></div></section>
 <section className="dashboard-panel form-section"><h2>Basic information</h2><div className="field-grid"><label>Display name<input value={form.display_name} onChange={set("display_name")} required/></label><label>Category<select value={form.category||"other"} onChange={set("category")}><option value="" disabled>Select a category</option>{!BUSINESS_CATEGORIES.includes(form.category)&&form.category?<option value={form.category}>{form.category}</option>:null}{BUSINESS_CATEGORIES.map(category=><option key={category} value={category}>{category.split(" ").map(word=>word.charAt(0).toUpperCase()+word.slice(1)).join(" ")}</option>)}</select></label></div><label>Description<textarea rows="5" value={form.description||""} onChange={set("description")} placeholder="Tell customers what you offer, what makes you different, and who you serve."/></label></section>
 <section className="dashboard-panel form-section"><h2>Contact and location</h2><div className="field-grid"><label>Phone<input value={form.phone_number||""} onChange={set("phone_number")}/></label><label>Email<input type="email" value={form.email||""} onChange={set("email")}/></label><label>Website<input value={form.website||""} onChange={set("website")}/></label><label>City<input value={form.city||""} onChange={set("city")}/></label><label className="wide-field">Address<input value={form.full_address||""} onChange={set("full_address")} placeholder="Street number and street name"/></label><label>Postal code<input value={form.postal_code||""} onChange={set("postal_code")}/></label></div><BusinessLocationPicker token={token} address={form.full_address} city={form.city} postalCode={form.postal_code} value={businessLocation} onChange={setBusinessLocation}/></section>
 <section className="dashboard-panel form-section hours-section">
  <div className="hours-title-row"><div><h2>Business hours</h2><p className="field-help">Choose when customers can visit or contact you. Turn a day off to mark it as closed.</p></div><div className="hours-copy-actions"><button type="button" className="secondary-action" onClick={()=>copyDay("monday",["tuesday","wednesday","thursday","friday"])}>Copy Monday to weekdays</button><button type="button" className="secondary-action" onClick={()=>copyDay("monday",DAYS.slice(1).map(d=>d.key))}>Copy Monday to all</button></div></div>
  <div className="hours-table" role="group" aria-label="Business hours">
   {DAYS.map(({key,label})=>{const day=businessHours[key]||DEFAULT_HOURS;return <div className={`hours-row ${day.closed?"is-closed":""}`} key={key}>
    <div className="hours-day"><strong>{label}</strong><label className="hours-open-toggle"><input type="checkbox" checked={!day.closed} onChange={e=>updateDay(key,{closed:!e.target.checked})}/><span>{day.closed?"Closed":"Open"}</span></label></div>
    <div className="hours-times">
     {day.closed?<span className="closed-day-label">Closed all day</span>:<><label><span>Opens</span><input type="time" value={day.open} onChange={e=>updateDay(key,{open:e.target.value})}/></label><span className="hours-to">to</span><label><span>Closes</span><input type="time" value={day.close} onChange={e=>updateDay(key,{close:e.target.value})}/></label></>}
    </div>
   </div>})}
  </div>
 </section>
 <section className="dashboard-panel form-section amenities-section">
  <div className="amenities-heading"><div><h2>Amenities & services</h2><p className="field-help">Select only what your business actually offers. Customers can see these details and use them when searching.</p></div><span className="owner-data-badge">Provided by business</span></div>
  <div className="amenity-groups">
   {AMENITY_GROUPS.map(group=><div className="amenity-group" key={group.key}><h3><span>{group.icon}</span>{group.title}</h3><div className="amenity-options">{group.options.map(([key,label])=><label className={`amenity-chip ${(amenities[group.key]||[]).includes(key)?"selected":""}`} key={key}><input type="checkbox" checked={(amenities[group.key]||[]).includes(key)} onChange={()=>toggleAmenity(group.key,key)}/><span>{label}</span></label>)}</div></div>)}
  </div>
  <div className="status-grid">
   <fieldset className="status-card"><legend>🥩 Halal status</legend><p>Choose the most accurate option. AskMyCity can distinguish a fully halal restaurant from one with only halal options.</p>{[["fully_halal","Fully halal"],["halal_options","Halal options available"],["not_halal","Not halal"],["unknown","Unknown"]].map(([value,label])=><label className="radio-option" key={value}><input type="radio" name="halal_status" value={value} checked={amenities.halal_status===value} onChange={e=>setAmenity("halal_status",e.target.value)}/><span>{label}</span></label>)}<label className="evidence-field">Verification URL (optional)<input type="url" value={amenities.halal_evidence_url||""} onChange={e=>setAmenity("halal_evidence_url",e.target.value)} placeholder="https://..."/></label><label className="evidence-field">Certificate / note (optional)<input value={amenities.halal_certificate_note||""} onChange={e=>setAmenity("halal_certificate_note",e.target.value)} placeholder="Certification body or note"/></label></fieldset>
   <fieldset className="status-card"><legend>🍷 Alcohol</legend><p>Tell customers what is served at this location.</p>{[["none","No alcohol served"],["beer_wine","Beer & wine only"],["full_bar","Full bar / cocktails"],["served","Alcohol served"],["unknown","Unknown"]].map(([value,label])=><label className="radio-option" key={value}><input type="radio" name="alcohol_status" value={value} checked={amenities.alcohol_status===value} onChange={e=>setAmenity("alcohol_status",e.target.value)}/><span>{label}</span></label>)}<div className="dietary-box"><strong>Dietary options</strong>{[["vegetarian","Vegetarian"],["vegan","Vegan"],["gluten_free","Gluten-free"]].map(([key,label])=><label className={`amenity-chip ${(amenities.dietary||[]).includes(key)?"selected":""}`} key={key}><input type="checkbox" checked={(amenities.dietary||[]).includes(key)} onChange={()=>toggleAmenity("dietary",key)}/><span>{label}</span></label>)}</div></fieldset>
  </div>
 </section>
 <section className="dashboard-panel form-section publish-section"><label className="publish-toggle"><input type="checkbox" checked={form.is_published} onChange={set("is_published")}/> Publish this profile</label><p className="field-help">Published profiles can appear in customer search results. Confirm your exact map pin before publishing.</p></section>
 {error&&<div className="dashboard-alert error">{error}</div>}{message&&<div className="dashboard-alert success">{message}</div>}<button className="dashboard-primary save-button">Save profile</button></form></DashboardShell>
}
function MediaSlot({title,item,wide,busy,onUpload,onDelete}){return <div className={`media-slot ${wide?"wide":""}`}><h3>{title}</h3>{item?<><img src={absoluteMediaUrl(item.file_url)} alt={title}/><div className="media-slot-actions"><label>Replace<input type="file" accept="image/jpeg,image/png,image/webp" disabled={busy} onChange={e=>onUpload(e.target.files?.[0])}/></label><button type="button" onClick={onDelete}>Remove</button></div></>:<label className="media-empty">{busy?"Uploading...":`Upload ${title.toLowerCase()}`}<input type="file" accept="image/jpeg,image/png,image/webp" disabled={busy} onChange={e=>onUpload(e.target.files?.[0])}/></label>}</div>}
