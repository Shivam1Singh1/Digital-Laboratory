<script setup>

import { ref, computed } from 'vue'
import axios from 'axios'
import { useUserStore } from '../../stores/user'
import { loginUrl } from '../../utils/frappeUrl'
import PageHeader from '../layout/PageHeader.vue'
import './Settings.css'

const userStore = useUserStore()


const fileInput = ref(null)
const uploading = ref(false)
const photoError = ref('')
const photoNotice = ref('')


const avatarFailed = ref(false)

const hasPhoto = computed(
  () => Boolean(userStore.user.user_image) && !avatarFailed.value
)


const AVATAR_PX = 512


const MAX_SOURCE_BYTES = 20 * 1024 * 1024


const resizeToSquare = (file) =>
  new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const img = new Image()

    img.onload = () => {
      URL.revokeObjectURL(url)

      const side = Math.min(img.naturalWidth, img.naturalHeight)
      if (!side) {
        reject(new Error('That image has no readable size.'))
        return
      }

      const out = Math.min(AVATAR_PX, side)
      const canvas = document.createElement('canvas')
      canvas.width = out
      canvas.height = out

      const ctx = canvas.getContext('2d')


      ctx.fillStyle = '#ffffff'
      ctx.fillRect(0, 0, out, out)
      ctx.imageSmoothingQuality = 'high'
      ctx.drawImage(
        img,
        (img.naturalWidth - side) / 2,
        (img.naturalHeight - side) / 2,
        side,
        side,
        0,
        0,
        out,
        out
      )

      canvas.toBlob(
        (blob) => (blob ? resolve(blob) : reject(new Error('Could not process that image.'))),
        'image/jpeg',
        0.9
      )
    }

    img.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('That file is not an image this browser can open.'))
    }

    img.src = url
  })

const pickPhoto = () => {
  photoError.value = ''
  photoNotice.value = ''
  fileInput.value?.click()
}

const onPhotoChosen = async (event) => {
  const file = event.target.files?.[0]

  event.target.value = ''
  if (!file) return

  if (!file.type.startsWith('image/')) {
    photoError.value = 'Choose an image file — JPG, PNG or GIF.'
    return
  }
  if (file.size > MAX_SOURCE_BYTES) {
    photoError.value = 'That file is unusually large. Please choose another photo.'
    return
  }

  uploading.value = true
  photoError.value = ''
  photoNotice.value = ''

  try {
    const square = await resizeToSquare(file)


    const form = new FormData()
    form.append('file', square, 'profile-photo.jpg')
    form.append('is_private', '0')

    const upload = await fetch('/api/method/upload_file', {
      method: 'POST',
      body: form,
      credentials: 'same-origin',
      headers: { 'X-Frappe-CSRF-Token': window.csrf_token || '' }
    })
    const uploaded = await upload.json()
    const url = uploaded?.message?.file_url
    if (!url) throw new Error('Upload did not return a file address.')

    const saved = await axios.post(
      '/api/method/elab_notebook.elab_notebook.api.user.set_profile_photo',
      { file_url: url }
    )

    userStore.setUserImage(saved.data?.message?.user_image || url)
    avatarFailed.value = false
    photoNotice.value = 'Photo updated.'
  } catch (err) {
    console.error('Profile photo upload failed', err)
    photoError.value =
      err.response?.data?.message || 'Could not save that photo. Please try again.'
  } finally {
    uploading.value = false
  }
}

const removePhoto = async () => {
  uploading.value = true
  photoError.value = ''
  photoNotice.value = ''
  try {
    await axios.post(
      '/api/method/elab_notebook.elab_notebook.api.user.remove_profile_photo'
    )
    userStore.setUserImage(null)
    avatarFailed.value = false
    photoNotice.value = 'Photo removed.'
  } catch (err) {
    console.error('Profile photo removal failed', err)
    photoError.value = 'Could not remove the photo. Please try again.'
  } finally {
    uploading.value = false
  }
}


const department = computed(() => {
  const names = userStore.employeeScope.function_names || []
  return names.length ? names.join(', ') : 'Not assigned'
})

const projectAccess = computed(() => {
  const scope = userStore.employeeScope
  if (scope.scope === 'all') return 'All projects'
  const n = (scope.projects || []).length
  return n === 1 ? '1 project' : `${n} projects`
})


const signingOut = ref(false)

const signOut = async () => {
  signingOut.value = true
  try {
    await axios.post('/api/method/logout')
  } catch (err) {
    console.error('Logout failed', err)
  }


  window.location.href = loginUrl()
}
</script>

<template>
  <div class="settings-container">
    <PageHeader
      :breadcrumbs="[{ label: 'Home', href: '/' }, { label: 'Settings' }]"
      title="Settings"
      subtitle="Your profile, and how the app looks on this computer."
    />

    <!-- ---------------------------------------------------------- profile -->
    <section class="settings-card">
      <h2 class="settings-card-title">Profile</h2>

      <div class="settings-identity">
        <div class="settings-avatar">
          <img
            v-if="hasPhoto"
            :src="userStore.user.user_image"
            class="avatar-img"
            :alt="userStore.user.full_name"
            @error="avatarFailed = true"
          />
          <div v-else class="settings-avatar-fallback">{{ userStore.user.initials }}</div>
        </div>

        <div class="settings-identity-body">
          <h3 class="settings-name">{{ userStore.user.full_name }}</h3>
          <p class="settings-role">{{ userStore.user.role }}</p>

          <input
            ref="fileInput"
            type="file"
            accept="image/*"
            class="settings-file-input"
            @change="onPhotoChosen"
          />
          <div class="settings-actions">
            <button class="btn btn-primary" type="button" :disabled="uploading" @click="pickPhoto">
              <span v-if="uploading" class="spinner btn-spinner"></span>
              {{ hasPhoto ? 'Change photo' : 'Upload photo' }}
            </button>
            <button
              v-if="hasPhoto"
              class="btn btn-secondary"
              type="button"
              :disabled="uploading"
              @click="removePhoto"
            >
              Remove
            </button>
          </div>

          <p v-if="photoError" class="settings-msg settings-msg--error">{{ photoError }}</p>
          <p v-else-if="photoNotice" class="settings-msg settings-msg--ok">{{ photoNotice }}</p>
          <p v-else class="settings-hint">
            Any photo works — it is cropped to a square and resized for you.
          </p>
        </div>
      </div>

      <dl class="settings-facts">
        <div>
          <dt>Email</dt>
          <dd>{{ userStore.user.name || '—' }}</dd>
        </div>
        <div>
          <dt>Employee ID</dt>
          <dd>{{ userStore.user.employee || 'Not linked' }}</dd>
        </div>
        <div>
          <dt>Department</dt>
          <dd>{{ department }}</dd>
        </div>
        <div>
          <dt>Project access</dt>
          <dd>{{ projectAccess }}</dd>
        </div>
      </dl>
    </section>

    <!-- ------------------------------------------------------- appearance -->
    <section class="settings-card">
      <h2 class="settings-card-title">Appearance</h2>
      <p class="settings-card-note">Applies to this browser only.</p>

      <div class="settings-themes">
        <button
          type="button"
          class="settings-theme"
          :class="{ active: userStore.theme === 'light' }"
          :aria-pressed="userStore.theme === 'light'"
          @click="userStore.setTheme('light')"
        >
          <span class="settings-swatch settings-swatch--day" aria-hidden="true"></span>
          <span class="settings-theme-text">
            <span class="settings-theme-name">Day</span>
            <span class="settings-theme-desc">Bright, for a lit bench</span>
          </span>
          <span class="settings-tick" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </span>
        </button>

        <button
          type="button"
          class="settings-theme"
          :class="{ active: userStore.theme === 'dark' }"
          :aria-pressed="userStore.theme === 'dark'"
          @click="userStore.setTheme('dark')"
        >
          <span class="settings-swatch settings-swatch--night" aria-hidden="true"></span>
          <span class="settings-theme-text">
            <span class="settings-theme-name">Night</span>
            <span class="settings-theme-desc">Dim, for long sessions</span>
          </span>
          <span class="settings-tick" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </span>
        </button>
      </div>

      <label class="settings-toggle">
        <input
          type="checkbox"
          class="settings-checkbox"
          :checked="userStore.rememberProject"
          @change="userStore.setRememberProject($event.target.checked)"
        />
        <span class="settings-toggle-text">
          <span class="settings-toggle-name">Remember my selected project</span>
          <span class="settings-toggle-desc">
            The project picker normally resets to <em>All</em> each time you sign in.
          </span>
        </span>
      </label>
    </section>

    <!-- ---------------------------------------------------------- account -->
    <section class="settings-card">
      <h2 class="settings-card-title">Account</h2>
      <div class="settings-signout">
        <p class="settings-card-note">
          You are signed in as <strong>{{ userStore.user.full_name }}</strong>.
        </p>
        <button class="btn btn-secondary settings-signout-btn" type="button" :disabled="signingOut" @click="signOut">
          <span v-if="signingOut" class="spinner btn-spinner"></span>
          Sign out
        </button>
      </div>
    </section>
  </div>
</template>
